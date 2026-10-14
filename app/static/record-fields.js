// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  const copy = value => JSON.parse(JSON.stringify(value));
  function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === 'object') {
      const result = Object.create(null);
      for (const key of Object.keys(value).sort()) result[key] = canonical(value[key]);
      return result;
    }
    return value;
  }
  function render(container, schema, data, readonly, onChange, onError) {
    container.replaceChildren();
    const baseline = copy(data), states = [];
    for (const [index, [key, spec]] of Object.entries(schema.properties || {}).entries()) {
      const present = own(data, key), required = (schema.required || []).includes(key);
      const group = document.createElement('fieldset'), label = document.createElement('label');
      const title = spec.title || key, id = 'record-field-' + index;
      label.textContent = title + (required ? ' (required)' : ''); label.setAttribute('for', id);
      const include = document.createElement('input'); include.type = 'checkbox'; include.id = id + '-include';
      include.checked = required || present; include.disabled = readonly || required;
      const presence = document.createElement('label'); presence.setAttribute('for', include.id);
      presence.append(include, document.createTextNode(' Include ' + title));
      const choices = own(spec, 'const') ? [spec.const] : spec.enum;
      let input;
      if (choices || spec.type === 'boolean' || spec.type === 'null') {
        input = document.createElement('select');
        const options = choices || (spec.type === 'boolean' ? [false, true] : [null]);
        for (const [number, value] of options.entries()) {
          const option = document.createElement('option'); option.value = String(number);
          option.textContent = typeof value === 'string' ? value : JSON.stringify(value); input.append(option);
        }
        const match = present ? options.findIndex(value => JSON.stringify(canonical(value)) === JSON.stringify(canonical(data[key]))) : -1;
        input.value = match >= 0 ? String(match) : '0';
        input.readValue = () => copy(options[Number(input.value)]);
      } else if (spec.type === 'object' || spec.type === 'array') {
        input = document.createElement('textarea'); input.rows = 5; input.maxLength = 65536;
        input.value = JSON.stringify(present ? data[key] : (spec.type === 'array' ? [] : {}), null, 2);
        input.readValue = () => JSON.parse(input.value);
      } else {
        input = document.createElement('input');
        input.type = ['integer', 'number'].includes(spec.type) ? 'number' : 'text';
        input.value = present ? String(data[key]) : '';
        if (spec.type === 'string') {
          input.maxLength = spec.maxLength === undefined ? 8192 : spec.maxLength;
          if (spec.minLength !== undefined) input.minLength = spec.minLength;
          input.readValue = () => input.value;
        } else {
          input.step = spec.type === 'integer' ? '1' : 'any';
          if (spec.minimum !== undefined) input.min = spec.minimum;
          if (spec.maximum !== undefined) input.max = spec.maximum;
          input.readValue = () => {
            if (input.value.trim() === '') throw new Error('Enter a number for ' + title + '.');
            const value = Number(input.value);
            if (!Number.isFinite(value) || (spec.type === 'integer' && !Number.isInteger(value))) throw new Error('Enter a valid ' + spec.type + ' for ' + title + '.');
            return value;
          };
        }
      }
      input.id = id; input.required = required; input.disabled = readonly || !include.checked || own(spec, 'const');
      group.append(label, input); if (!required) group.append(presence);
      if (spec.description) { const hint = document.createElement('p'); hint.textContent = spec.description; group.append(hint); }
      container.append(group); states.push({key, input, include, readonly});
      const changed = () => {
        if (readonly) return;
        input.disabled = !include.checked || own(spec, 'const');
        try { const value = collect(); onChange(value); onError(''); }
        catch (_) { onError('Check the field values and any nested JSON.'); }
      };
      input.addEventListener('input', changed); input.addEventListener('change', changed); include.addEventListener('change', changed);
    }
    function collect() {
      const result = copy(baseline);
      for (const {key, input, include} of states) {
        if (!include.checked) { delete result[key]; continue; }
        Object.defineProperty(result, key, {value: input.readValue(), enumerable:true, writable:true, configurable:true});
      }
      return result;
    }
    return { collect, states };
  }
  globalThis.C0RecordFields = { render };
})();
