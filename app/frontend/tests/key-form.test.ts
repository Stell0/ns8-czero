import { expect, it } from 'vitest'
import { keyRequest } from '../src/api/key-form'
const id = '11111111-1111-4111-8111-111111111111'
const spaces = [{ id, role: 'reader' }]
const form = {
  name: ' Workflow ',
  days: '90',
  neverExpires: false,
  write: false,
  selected: { [id]: true },
}
it('requires current grants and checks every write selection', () => {
  expect(keyRequest(form, spaces)).toEqual({
    name: 'Workflow',
    lifetime_days: 90,
    space_ids: [id],
    scopes: ['c0:read'],
  })
  expect(() => keyRequest({ ...form, write: true }, spaces)).toThrow()
  expect(() => keyRequest(form, [])).toThrow()
  expect(
    keyRequest({ ...form, write: true }, [{ id, role: 'editor' }]).scopes,
  ).toEqual(['c0:read', 'c0:write'])
})
it('rejects invalid names and missing spaces', () => {
  for (const changed of [{ name: '' }, { selected: {} }])
    expect(() => keyRequest({ ...form, ...changed }, spaces)).toThrow()
})

it('requires a whole lifetime from 1 to 365 unless never expires is selected', () => {
  for (const days of ['', ' ', '0', '-1', '366', '1.5', 'oops', 'Infinity']) {
    expect(() => keyRequest({ ...form, days }, spaces)).toThrowError(
      expect.objectContaining({ status: 422, code: 'key_lifetime' }),
    )
    expect(
      keyRequest({ ...form, days, neverExpires: true }, spaces).lifetime_days,
    ).toBeNull()
  }
  for (const days of ['1', '90', '365'])
    expect(keyRequest({ ...form, days }, spaces).lifetime_days).toBe(
      Number(days),
    )
  expect(() => keyRequest({ ...form, neverExpires: true }, [])).toThrow()
  expect(() =>
    keyRequest({ ...form, neverExpires: true, write: true }, spaces),
  ).toThrow()
})
