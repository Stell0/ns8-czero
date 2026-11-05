import { expect, it } from 'vitest'
import {
  renderTokens,
  safeURL,
  type Token,
  type Heading,
} from '../src/components/markdown'
function token(type: string, content = '', tag = '', nesting = 0): Token {
  return { type, content, tag, nesting }
}
it('renders hostile HTML as text and never activates images or unsafe links', () => {
  const target = document.createElement('article'),
    headings: Heading[] = []
  const tokens = [
    token(
      'html_block',
      '<script>alert(1)</script><img src="https://example.org/track">',
    ),
    token('image', 'external image'),
    {
      ...token('link_open', '', 'a', 1),
      attrs: [['href', 'javascript:alert(1)']] as [string, string][],
    },
    token('text', 'unsafe'),
    token('link_close', '', 'a', -1),
  ]
  for (const value of renderTokens(
    target,
    tokens,
    headings,
    (text) => `Image: ${text}`,
  ))
    void value
  expect(target.querySelector('script,img,a')).toBeNull()
  expect(target.textContent).toContain('<script>')
  expect(target.textContent).toContain('Image: external image')
})
it('rejects unsafe protocols and embedded credentials', () => {
  for (const url of [
    'javascript:alert(1)',
    'data:text/html,<script>',
    'https://example.org/\nunsafe',
    'https://example.org/ unsafe',
    'https://example.org/\u007funsafe',
    'https://user:secret@example.org/',
  ])
    expect(safeURL(url)).toBeNull()
  expect(safeURL('https://example.org/evidence')).toBe(
    'https://example.org/evidence',
  )
})
it('builds headings and local contents anchors from literal tokens', () => {
  const target = document.createElement('article'),
    headings: Heading[] = []
  const inline = {
    ...token('inline'),
    children: [token('text', 'A <safe> heading')],
  }
  for (const value of renderTokens(
    target,
    [
      token('heading_open', '', 'h1', 1),
      inline,
      token('heading_close', '', 'h1', -1),
    ],
    headings,
    (text) => text,
  ))
    void value
  expect(target.querySelector('h2')?.textContent).toBe('A <safe> heading')
  expect(headings).toEqual([
    { id: 'article-heading-1', label: 'A <safe> heading' },
  ])
})
