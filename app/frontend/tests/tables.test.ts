import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import RecordValue from '../src/components/RecordValue.vue'
import en from '../src/locales/en.json'
import { fieldLabel, preview, scalar } from '../src/api/tables'
const plugins = [createI18n({ legacy: false, locale: 'en', messages: { en } })]
describe('generic record values', () => {
  it('distinguishes absent, null, empty, false and zero', () => {
    for (const [value, text] of [
      [undefined, 'Not present'],
      [null, 'Null'],
      ['', 'Empty text'],
      [false, 'No'],
      [0, '0'],
    ]) {
      expect(
        mount(RecordValue, { props: { value }, global: { plugins } }).text(),
      ).toBe(text)
    }
  })
  it('renders nested arrays as tables without interpreting stored markup', () => {
    const wrapper = mount(RecordValue, {
      props: {
        value: [{ name: '<img src=x onerror=alert(1)>' }],
        schema: {
          type: 'array',
          items: { type: 'object', properties: { name: { type: 'string' } } },
        },
        expanded: true,
      },
      global: { plugins },
    })
    expect(wrapper.findAll('table')).toHaveLength(1)
    expect(wrapper.text()).toContain('<img src=x onerror=alert(1)>')
    expect(wrapper.findAll('img')).toHaveLength(0)
  })
  it('keeps long text accessible in the expanded view', () => {
    const value = 'a'.repeat(200)
    expect(preview(value)).toHaveLength(121)
    expect(
      mount(RecordValue, {
        props: { value, expanded: true },
        global: { plugins },
      }).text(),
    ).toBe(value)
    expect(fieldLabel('external_key')).toBe('External key')
    expect(scalar({ type: 'array' })).toBe(false)
  })
})
