import { expect, it } from 'vitest'
import { keyRequest } from '../src/api/key-form'
const id = '11111111-1111-4111-8111-111111111111'
const spaces = [{ id, role: 'reader' }]
const form = {
  name: ' Workflow ',
  days: '90',
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
it('rejects invalid names, missing spaces and unbounded lifetimes', () => {
  for (const changed of [
    { name: '' },
    { selected: {} },
    { days: '0' },
    { days: '366' },
    { days: '1.5' },
    { days: 'oops' },
  ])
    expect(() => keyRequest({ ...form, ...changed }, spaces)).toThrow()
  expect(keyRequest({ ...form, days: '' }, spaces).lifetime_days).toBeNull()
})
