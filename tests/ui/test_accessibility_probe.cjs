// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../accessibility_probe.js'), 'utf8');

function element(tagName, options = {}) {
  return {
    tagName, type: 'text', textContent: '', labels: [], value: '',
    getClientRects() { return options.hidden ? [] : [{}]; },
    closest() { return options.ariaHidden || null; },
    getAttribute(name) { return options.attributes?.[name] || null; },
    querySelector() { return options.image || null; },
    ...options,
  };
}
function documentFixture(options = {}) {
  const ids = {'main-content': {}, label: {textContent: 'private fixture label'}};
  const controls = [
    element('INPUT', {labels: [{textContent: 'Input label'}]}),
    element('SELECT', {attributes: {'aria-label': 'Select label'}}),
    element('TEXTAREA', {attributes: {'aria-labelledby': 'label'}}),
    element('BUTTON', {textContent: 'Save'}),
  ];
  const links = [element('A', {textContent: 'Records'}), element('A', {image: {alt: 'Home'}})];
  const document = {
    documentElement: {lang: 'en'},
    getElementById(id) { return ids[id] || null; },
    querySelector(selector) {
      if (selector === 'main') return options.noMain ? null : {};
      if (selector === '.skip-link') return element('A', {attributes: {href: options.skipTarget || (options.badTarget ? '#missing' : '#main-content')}});
      return options.noNavigation ? null : {};
    },
    querySelectorAll(selector) {
      if (selector === 'h1') return options.extraHeading ? [{}, {}] : [{}];
      return selector === 'a[href]' ? links : controls;
    },
  };
  document.baseURI=options.baseURI;
  return {document, controls, links};
}
function run(fixture) {
  const check = vm.runInNewContext(source, {document: fixture.document, URL, window:{location:{href:'https://c0.example.test/admin/spaces?space_id=selected'}},
    getComputedStyle: () => ({visibility: 'visible'})});
  return JSON.parse(JSON.stringify(check()));
}
test('checks actual callback names, labels and landmarks without returning private text', () => {
  const result = run(documentFixture());
  assert.equal(result.controls_checked, 4);
  assert.equal(result.links_checked, 2);
  for (const key of Object.keys(result).filter(key => !key.endsWith('_checked'))) assert.equal(result[key], 0);
  assert(!JSON.stringify(result).includes('private fixture'));
});
test('rejects unlabeled controls and links, including disabled Reader fields', () => {
  const fixture = documentFixture();
  fixture.controls.push(element('INPUT', {disabled: true}));
  fixture.links.push(element('A'));
  assert.equal(run(fixture).unnamed_controls, 1);
  assert.equal(run(fixture).unnamed_links, 1);
});
test('does not substitute a placeholder or current field value for a label', () => {
  const fixture = documentFixture();
  fixture.controls.push(element('INPUT', {placeholder: 'Name', value: 'private value'}));
  assert.equal(run(fixture).unnamed_controls, 1);
});
test('skips nonvisible controls while checking named input buttons', () => {
  const fixture = documentFixture();
  fixture.controls.push(element('INPUT', {type: 'hidden'}), element('INPUT', {hidden: true}),
    element('INPUT', {type: 'submit', value: 'Save'}));
  assert.equal(run(fixture).controls_checked, 5);
  assert.equal(run(fixture).unnamed_controls, 0);
});
for (const [option, field] of [['noMain', 'missing_main'], ['noNavigation', 'missing_navigation'],
  ['extraHeading', 'missing_h1'], ['badTarget', 'missing_skip_target']]) {
  test('rejects missing accessible structure: ' + field, () => {
    assert.equal(run(documentFixture({[option]: true}))[field], 1);
  });
}
test('rejects missing document language', () => {
  const fixture = documentFixture(); fixture.document.documentElement.lang = '';
  assert.equal(run(fixture).missing_language, 1);
});

test('survives Robot Browser function conversion with leading license comments', () => {
  // Browser 19.14.2 applies new Function("return " + script) before page.evaluate.
  // A leading line comment after return causes automatic semicolon insertion.
  const fixture = documentFixture();
  const check = vm.runInNewContext('new Function(' + JSON.stringify('return ' + source) + ')()',
    {document: fixture.document, URL, window:{location:{href:'https://c0.example.test/admin/spaces?space_id=selected'}}, getComputedStyle: () => ({visibility: 'visible'})});
  assert.equal(typeof check, 'function');
  assert.equal(check().unnamed_controls, 0);
  const unwrapped = source.slice(source.indexOf('\n') + 1, source.lastIndexOf('\n)'));
  assert.equal(vm.runInNewContext('new Function(' + JSON.stringify('return ' + unwrapped) + ')()'), undefined);
});


test('accepts an explicit skip destination only on the same document and query',()=>{
  assert.equal(run(documentFixture({baseURI:'https://c0.example.test/',skipTarget:'https://c0.example.test/admin/spaces?space_id=selected#main-content'})).missing_skip_target,0);
});
for(const [title,options] of [
  ['fragment resolved against another base document',{baseURI:'https://c0.example.test/'}],
  ['another page',{skipTarget:'/wiki?space_id=selected#main-content'}],
  ['another space selection',{skipTarget:'?space_id=other#main-content'}],
  ['an external origin',{skipTarget:'https://other.example.test/admin/spaces?space_id=selected#main-content'}],
])test('rejects a skip link to '+title,()=>{
  assert.equal(run(documentFixture(options)).missing_skip_target,1);
});
