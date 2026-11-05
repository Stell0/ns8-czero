import { expect, it } from 'vitest'
import { contentLink } from '../src/api/content-links'
const base = 'https://c0.example.test/czero/czero17/'
const id = '11111111-1111-4111-8111-111111111111'
it('resolves stored typed links retaining exact revisions and selected space', () => {
  const url = new URL(
    contentLink(`${base}wiki?page_id=${id}&revision=7`, base, 'selected'),
  )
  expect(url.pathname).toBe(`/czero/czero17/wiki/${id}`)
  expect(url.searchParams.get('revision')).toBe('7')
  expect(url.searchParams.get('space_id')).toBe('selected')
  const document = new URL(
    contentLink(
      `${base}sources?document=${id}&snapshot=${id}&space_id=explicit`,
      base,
      'selected',
    ),
  )
  expect(document.pathname).toBe(`/czero/czero17/sources/${id}`)
  expect(document.searchParams.get('revision_id')).toBe(id)
  expect(document.searchParams.get('space_id')).toBe('explicit')
})
it('leaves external, different mount and ambiguous links unchanged', () => {
  for (const link of [
    `https://evidence.example.test/wiki?page=${id}`,
    `https://c0.example.test/other/wiki?page=${id}`,
    `${base}wiki?page=${id}&page=${id}`,
    `${base}wiki?page=${id}&page_id=${id}`,
    `${base}wiki?page=invalid&page_id=${id}`,
    `${base}sources?chunk=invalid&source=${id}`,
    `${base}sources?document=${id}&document=${id}&source=${id}`,
  ])
    expect(contentLink(link, base)).toBe(link)
})
it('preserves invalid and duplicate snapshots for exact-selector rejection', () => {
  for (const snapshots of [
    'snapshot=',
    'snapshot=invalid',
    `snapshot=${id}&snapshot=${id}`,
    `revision_id=${id}&snapshot=${id}`,
  ]) {
    const before = new URL(`${base}sources?document=${id}&${snapshots}`)
    const after = new URL(contentLink(before.href, base))
    expect(after.pathname).toBe(`/czero/czero17/sources/${id}`)
    expect(after.searchParams.getAll('revision_id')).toEqual([
      ...before.searchParams.getAll('revision_id'),
      ...before.searchParams.getAll('snapshot'),
    ])
  }
})
