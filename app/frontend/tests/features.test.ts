import { afterEach, expect, it } from 'vitest'
import { automaticSourcesAvailable } from '../src/api/features'
afterEach(() => {
  document.body.innerHTML = ''
})
it('shows native source controls only for an installed server capability', () => {
  expect(automaticSourcesAvailable()).toBe(false)
  for (const [value, expected] of [
    [true, true],
    [false, false],
    ['true', false],
  ]) {
    document.body.innerHTML = `<script type="application/json" id="c0-boot">${JSON.stringify({ features: { automatic_sources: value } })}</script>`
    expect(automaticSourcesAvailable()).toBe(expected)
  }
  document.body.innerHTML =
    '<script type="application/json" id="c0-boot">invalid</script>'
  expect(automaticSourcesAvailable()).toBe(false)
})
