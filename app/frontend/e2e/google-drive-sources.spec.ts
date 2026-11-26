import { expect, test, type Page } from '@playwright/test'
import { api, shared, source } from './fixtures'

const base = '/api/v1/automatic-sources'
const folder = 'https://drive.google.com/drive/folders/exampleFolder'
async function setup(page: Page, role = 'editor') {
  await api(page, role)
  await page.route(
    'http://127.0.0.1:4173/automatic-sources?*',
    async (route) => {
      const response = await route.fetch()
      await route.fulfill({
        response,
        body: (await response.text()).replace(
          '<head>',
          '<head><meta name="c0-automatic-sources" content="true">',
        ),
      })
    },
  )
}

for (const language of ['en', 'it']) {
  test(`Drive dropdown, folder preview and paused save in ${language}`, async ({
    page,
  }) => {
    const en = language === 'en'
    await setup(page)
    await page.setViewportSize({ width: en ? 1440 : 390, height: 960 })
    await page.addInitScript(
      ({ language, theme }) => {
        localStorage.setItem('c0-language', language)
        localStorage.setItem('c0-theme', theme)
      },
      { language, theme: en ? 'light' : 'dark' },
    )
    const savedDefinition = {
      id: source,
      name: 'My notes',
      kind: 'google_drive',
      config: {},
      enabled: false,
      revision: 1,
      interval_seconds: null,
      owner_id: 'fixture-account',
      next_run_at: null,
      last_success_at: null,
    }
    let saved = false,
      connected = false,
      previews = 0
    await page.route('**/api/v1/automatic-sources**', async (route) => {
      const req = route.request()
      const url = new URL(req.url())
      expect(url.searchParams.get('space_id')).toBe(shared)
      if (req.method() !== 'GET')
        expect(req.headers()['x-c0-csrf']).toBe('fixture-csrf')
      switch (url.pathname) {
        case base:
          return route.fulfill({
            json: { definitions: saved ? [savedDefinition] : [] },
          })
        case base + '/google-drive/connection':
          if (req.method() === 'DELETE') connected = false
          return route.fulfill({
            json: { available: true, connected, offline: connected },
          })
        case base + '/google-drive/connect':
          expect(req.postDataJSON()).toEqual({ offline: true })
          connected = true
          return route.fulfill({
            json: {
              url: 'https://accounts.google.com/o/oauth2/v2/auth?state=fixture',
            },
          })
        case base + '/google-drive/preview':
          expect(req.postDataJSON()).toEqual({
            folder_url: folder,
            identifier: null,
            expected_revision: null,
          })
          previews++
          return route.fulfill({
            json: {
              folder_name: 'My notes',
              preview_token: 'fixture-proof',
              complete: false,
              items: [
                { title: 'Procedure', outcome: 'include', reason: 'supported' },
                {
                  title: 'Recording.mp4',
                  outcome: 'skip',
                  reason: 'unsupported_format',
                },
                { title: 'Archive', outcome: 'skip', reason: 'subfolder' },
              ],
            },
          })
        case base + '/google-drive/save':
          expect(req.postDataJSON()).toEqual({
            preview_token: 'fixture-proof',
            name: 'My notes',
            enabled: false,
            interval_seconds: null,
            identifier: null,
            expected_revision: null,
            idempotency_key: expect.any(String),
          })
          saved = true
          return route.fulfill({ json: { id: source, revision: 1 } })
        default:
          return route.abort()
      }
    })
    // Exercise actual top-level navigation and C0's callback landing route while
    // keeping Google-account access independent of deterministic browser CI.
    await page.route(
      'https://accounts.google.com/o/oauth2/v2/auth?*',
      (route) =>
        route.fulfill({
          contentType: 'text/html',
          body: `<script>location.replace('http://127.0.0.1:4173/automatic-sources?space_id=${shared}&google_drive=connected&offline=1')</script>`,
        }),
    )
    await page.goto(`/automatic-sources?space_id=${shared}`)
    await page
      .getByRole('button', {
        name: en ? 'Add automatic source' : 'Aggiungi fonte automatica',
        exact: true,
      })
      .press('Enter')
    const dialog = page.getByRole('dialog')
    const type = dialog.getByRole('button', {
      name: en ? /Source type/ : /Tipo di fonte/,
    })
    const start = dialog.getByRole('textbox', {
      name: en ? 'Starting URLs' : 'URL iniziali',
      exact: true,
    })
    await start.fill('https://docs.example.org/')
    const select = async (label: string) => {
      await type.press('Enter')
      await page.getByRole('option', { name: label, exact: true }).click()
    }
    await select('GitHub')
    const repo = dialog.getByRole('textbox', { name: /owner\/repository_name/ })
    await expect(repo).toHaveValue('')
    await repo.fill('example/manuals')
    await select(en ? 'Website' : 'Sito web')
    await expect(start).toHaveValue('https://docs.example.org/')
    await select('GitHub')
    await expect(repo).toHaveValue('example/manuals')
    await select(en ? 'Google Drive folder' : 'Cartella di Google Drive')
    await expect(
      dialog.getByText(
        en
          ? /read files across your Drive/
          : /leggere i file in tutto il tuo Drive/,
      ),
    ).toBeVisible()
    await dialog
      .getByRole('checkbox', {
        name: en
          ? /Allow background updates/
          : /Consenti gli aggiornamenti in background/,
      })
      .check()
    await dialog
      .getByRole('button', {
        name: en ? 'Connect Google account' : 'Connetti account Google',
        exact: true,
      })
      .click()
    await expect(dialog.getByRole('status')).toHaveText(
      en ? /Google account connected/ : /Account Google connesso/,
    )
    const link = dialog.getByRole('textbox', {
      name: en ? 'Folder link' : 'Link alla cartella',
      exact: true,
    })
    await link.fill(folder)
    const preview = dialog.getByRole('button', {
      name: en ? 'Preview' : 'Anteprima',
      exact: true,
    })
    const save = dialog.getByRole('button', {
      name: en ? 'Save configuration' : 'Salva configurazione',
      exact: true,
    })
    await preview.click()
    await expect(
      dialog.getByRole('heading', { name: /My notes/ }),
    ).toBeFocused()
    await expect(
      dialog.getByText(
        en ? 'Skip · Unsupported format' : 'Escludi · Formato non supportato',
      ),
    ).toBeVisible()
    await expect(
      dialog.getByText(en ? 'Skip · Subfolder' : 'Escludi · Sottocartella'),
    ).toBeVisible()
    await expect(
      dialog.getByText(en ? /sample covers part/ : /campione copre parte/),
    ).toBeVisible()
    await expect(dialog.getByText(/· Shared/)).toBeVisible()
    const title = dialog.getByRole('textbox', {
      name: en ? 'Title' : 'Titolo',
      exact: true,
    })
    await expect(title).toHaveValue('My notes')
    await link.fill(folder + '2')
    await expect(dialog.getByRole('heading', { name: /My notes/ })).toHaveCount(
      0,
    )
    await save.click()
    await expect(dialog.getByRole('alert')).toHaveText(
      en ? /Preview the folder/ : /Visualizza l’anteprima/,
    )
    expect(saved).toBe(false)
    await link.fill(folder)
    await preview.click()
    // The new folder proof is returned asynchronously; keyboard activation
    // must wait until the user can review the replacement preview.
    await expect(
      dialog.getByRole('heading', { name: /My notes/ }),
    ).toBeFocused()
    await expect(save).toBeEnabled()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    await save.press('Enter')
    await expect(dialog).toHaveCount(0)
    await expect(page.getByRole('row', { name: /My notes/ })).toContainText(
      en ? 'Paused' : 'In pausa',
    )
    expect(previews).toBe(2)
  })
}
test('readers never request the Google connection and other editors cannot use its owner actions', async ({
  page,
}) => {
  const peer = {
    id: source,
    name: 'Private source',
    kind: 'google_drive',
    config: {},
    owner_id: 'different-account',
    enabled: true,
    interval_seconds: null,
    revision: 4,
    next_run_at: null,
    last_success_at: null,
  }
  let reads = 0
  await setup(page, 'reader')
  await page.route('**/api/v1/automatic-sources**', (route) => {
    if (
      new URL(route.request().url()).pathname ===
      base + '/google-drive/connection'
    ) {
      reads++
      return route.fulfill({
        json: { available: true, connected: true, offline: true },
      })
    }
    return route.fulfill({ json: { definitions: [peer] } })
  })
  await page.goto(`/automatic-sources?space_id=${shared}`)
  const row = page.getByRole('row', { name: /Private source/ })
  await expect(row).toBeVisible()
  await expect(row.getByRole('button', { name: 'Pause updates' })).toHaveCount(
    0,
  )
  expect(reads).toBe(0)
  await page.route('**/api/v1/me', (route) =>
    route.fulfill({
      json: {
        id: 'fixture-account',
        username: 'Peer',
        role: 'editor',
        csrf_token: 'fixture-csrf',
      },
    }),
  )
  await page.route('**/api/v1/spaces?*', (route) =>
    route.fulfill({
      json: {
        spaces: [{ id: shared, name: 'Shared', shared: true, role: 'editor' }],
      },
    }),
  )
  await page.reload()
  await expect(row.getByRole('button', { name: 'Pause updates' })).toBeVisible()
  await expect(
    row.getByRole('button', { name: 'Remove configuration' }),
  ).toBeVisible()
  await expect(row.getByRole('button', { name: 'Edit source' })).toHaveCount(0)
  await expect(row.getByRole('button', { name: 'Update now' })).toHaveCount(0)
})
