// Stored knowledge can contain earlier C0 citation URLs. Resolve their typed
// identities into current links without adding legacy website routes or rebinding
// an exact revision. Never rewrite a link belonging to another origin.
export function contentLink(href: string, website: string, space?: string) {
  const url = new URL(href)
  const base = new URL(website)
  const prefix = base.pathname.replace(/\/$/, '')
  if (url.origin !== base.origin || !url.pathname.startsWith(prefix + '/'))
    return href
  const id = (name: string) => {
    const values = url.searchParams.getAll(name)
    return values.length === 1 &&
      /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(values[0])
      ? values[0]
      : null
  }
  if (url.pathname === prefix + '/wiki') {
    const page = id('page') || id('page_id')
    if (page) {
      url.pathname = prefix + '/wiki/' + page
      url.searchParams.delete('page')
      url.searchParams.delete('page_id')
    }
  } else if (url.pathname === prefix + '/sources') {
    const chunk = id('chunk'),
      document = id('document'),
      source = id('source')
    if (chunk) url.pathname = prefix + '/evidence/' + chunk
    else if (document || source)
      url.pathname = prefix + '/sources/' + (document || source)
    if (chunk || document || source) {
      for (const key of ['chunk', 'document', 'source'])
        url.searchParams.delete(key)
      if (id('snapshot')) {
        url.searchParams.set('revision_id', id('snapshot')!)
        url.searchParams.delete('snapshot')
      }
    }
  }
  if (
    space &&
    !url.searchParams.has('space_id') &&
    /^\/(?:wiki|sources|evidence|explore)(?:\/|$)/.test(
      url.pathname.slice(prefix.length),
    )
  )
    url.searchParams.set('space_id', space)
  return url.href
}
