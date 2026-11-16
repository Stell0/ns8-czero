import { afterEach, expect, it } from 'vitest'
import { automaticSourcesAvailable } from '../src/api/features'
afterEach(() => {
  document.body.innerHTML = ''
})
it('shows native source controls only for an installed server capability', () => {
  expect(automaticSourcesAvailable()).toBe(false)
  for (const [value, expected] of [
    ['true', true],
    ['false', false],
    ['TRUE', false],
    ['1', false],
    ['', false],
  ]) {
    document.body.innerHTML = `<meta name="c0-automatic-sources" content="${value}">`
    expect(automaticSourcesAvailable()).toBe(expected)
  }
  document.body.innerHTML = '<meta name="c0-automatic-sources">'
  expect(automaticSourcesAvailable()).toBe(false)
})
