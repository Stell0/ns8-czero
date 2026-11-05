import { type Page } from '@playwright/test'
export const shared = '11111111-1111-4111-8111-111111111111'
export const privateSpace = '22222222-2222-4222-8222-222222222222'
export const article = '33333333-3333-4333-8333-333333333333'
export const source = '44444444-4444-4444-8444-444444444444'
export const version = '55555555-5555-4555-8555-555555555555'
export const fixturePage = {
  id: article,
  slug: 'manual/setup',
  title: 'Fixture manual',
  revision: 1,
  updated_at: '2026-01-01T12:00:00Z',
}
export async function api(page: Page, role = 'reader') {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1/', '')
    let value: unknown
    if (path === 'me')
      value = {
        id: 'fixture-account',
        username: 'Alice',
        role,
        csrf_token: 'fixture-csrf',
      }
    else if (path === 'spaces')
      value = {
        spaces: [
          { id: shared, name: 'Knowledge space Shared', shared: true, role },
          { id: privateSpace, name: 'Protected', shared: false, role },
        ],
      }
    else if (path === 'wiki/pages') value = { pages: [fixturePage] }
    else if (path === `wiki/pages/${article}`)
      value = {
        ...fixturePage,
        content: {
          number: 1,
          title: fixturePage.title,
          body: '# Configuration\n\nRetained knowledge.\n\n<script>window.pwned=true</script>\n\n![image](https://example.org/tracker)\n\n## Verify\n\nFinal checks.',
        },
      }
    else if (path === 'claims') value = { claims: [] }
    else if (path === 'source-documents')
      value = {
        documents: [
          {
            id: source,
            title: 'Source manual',
            state: 'ready',
            media_type: 'text/markdown',
          },
        ],
      }
    else if (path === `source-documents/${source}`)
      value = {
        id: source,
        title: 'Source manual',
        state: 'ready',
        media_type: 'text/markdown',
        body: '# Published evidence\n\nOriginal published document.',
        metadata: {},
        multipart: false,
        parts: [{ source_id: source, version_id: version }],
        original_version_ids: [],
      }
    else if (path === `sources/${source}`)
      value = {
        id: source,
        title: 'Source manual',
        revision: 3,
        metadata: {},
        deleted: false,
      }
    else if (path === `sources/${source}/versions`)
      value = {
        versions: [
          {
            id: version,
            source_id: source,
            state: 'ready',
            generation: 1,
            original_present: false,
          },
        ],
      }
    else if (path === `sources/${source}/extraction`)
      value = { state: 'ready', run: null, current_available: true }
    else if (path === 'oauth/connections') value = { connections: [] }
    else if (path === 'api-keys') value = { api_keys: [] }
    else if (path === 'entities') value = { entities: [] }
    else if (path === 'object-types') value = { types: [] }
    else if (path === 'knowledge/search')
      value = {
        hits: [
          {
            id: article,
            title: fixturePage.title,
            excerpt: 'Retained knowledge.',
            kind: 'wiki_revision',
            wiki: { page_id: article, revision: 1 },
            citation: null,
          },
        ],
      }
    else
      return route.fulfill({ status: 404, json: { detail: 'fixture_missing' } })
    await route.fulfill({ json: value })
  })
}
