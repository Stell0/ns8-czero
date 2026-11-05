// Ported from C0's allowlisted renderer. Stored HTML/media never become active.
export interface Token {
  type: string
  tag: string
  nesting: number
  content: string
  attrs?: [string, string][]
  children?: Token[]
}
export interface Heading {
  id: string
  label: string
}
export function safeURL(value: string, base = location.href) {
  if (!value || /[\x00-\x20\x7f]/.test(value)) return null
  try {
    const url = new URL(value, base)
    return ['http:', 'https:'].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : null
  } catch {
    return null
  }
}
export function* renderTokens(
  container: HTMLElement,
  tokens: Token[],
  headings: Heading[],
  imageLabel: (text: string) => string,
  linkBase = location.href,
  resolveLink = (href: string) => href,
) {
  const stack: HTMLElement[] = [container]
  const allowed = new Set([
    'p',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'blockquote',
    'ul',
    'ol',
    'li',
    'strong',
    'em',
    's',
    'table',
    'thead',
    'tbody',
    'tr',
    'th',
    'td',
  ])
  function node(tag: string, text?: string) {
    const element = document.createElement(tag)
    if (text) element.textContent = text
    return element
  }
  function* render(items: Token[]): Generator<void> {
    for (const [index, token] of items.entries()) {
      yield
      const parent = stack[stack.length - 1]
      if (token.type === 'inline') {
        yield* render(token.children || [])
        continue
      }
      if (['text', 'html_inline', 'html_block'].includes(token.type)) {
        parent.append(document.createTextNode(token.content))
        continue
      }
      if (token.type === 'softbreak') {
        parent.append(document.createTextNode('\n'))
        continue
      }
      if (token.type === 'hardbreak') {
        parent.append(node('br'))
        continue
      }
      if (token.type === 'code_inline') {
        parent.append(node('code', token.content))
        continue
      }
      if (['fence', 'code_block'].includes(token.type)) {
        const pre = node('pre')
        pre.append(node('code', token.content))
        parent.append(pre)
        continue
      }
      if (token.type === 'image') {
        parent.append(node('span', imageLabel(token.content)))
        continue
      }
      if (token.type === 'hr') {
        parent.append(node('hr'))
        continue
      }
      if (token.nesting === -1) {
        if (stack.length > 1) stack.pop()
        continue
      }
      if (token.type === 'link_open') {
        const href = safeURL(
          token.attrs?.find(([key]) => key === 'href')?.[1] || '',
          linkBase,
        )
        const link = node(href ? 'a' : 'span')
        if (href) {
          link.setAttribute('href', resolveLink(href))
          link.setAttribute('rel', 'noopener noreferrer')
          link.setAttribute('referrerpolicy', 'no-referrer')
        }
        parent.append(link)
        stack.push(link)
        continue
      }
      if (token.nesting === 1 && allowed.has(token.tag)) {
        const heading = /^h[1-6]$/.test(token.tag)
        const child = node(
          heading ? `h${Math.min(6, Number(token.tag[1]) + 1)}` : token.tag,
        )
        if (heading) {
          child.id = `article-heading-${headings.length + 1}`
          headings.push({
            id: child.id,
            label: (items[index + 1]?.children || [])
              .map((part) => part.content || '')
              .join(''),
          })
        }
        if (token.tag === 'ol') {
          const start = token.attrs?.find(([key]) => key === 'start')?.[1]
          if (start && /^\d{1,9}$/.test(start))
            child.setAttribute('start', start)
        }
        parent.append(child)
        stack.push(child)
      }
    }
  }
  yield* render(tokens)
}
