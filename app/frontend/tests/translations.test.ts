import { expect, it } from 'vitest'
import en from '../src/locales/en.json'
import itCatalog from '../src/locales/it.json'
function keys(value: object, prefix = ''): string[] {
  return Object.entries(value)
    .flatMap(([key, item]) =>
      typeof item === 'object'
        ? keys(item, `${prefix}${key}.`)
        : [`${prefix}${key}`],
    )
    .sort()
}
it('ships matching English and Italian keys', () => {
  expect(keys(itCatalog)).toEqual(keys(en))
})
it('keeps placeholder contracts in Italian', () => {
  function compare(left: object, right: object) {
    for (const key in left) {
      const a = left[key as keyof typeof left],
        b = right[key as keyof typeof right]
      if (typeof a === 'object') compare(a, b)
      else
        expect(String(b).match(/\{[^}]+\}/g) || []).toEqual(
          String(a).match(/\{[^}]+\}/g) || [],
        )
    }
  }
  compare(en, itCatalog)
})
