import { expect, test } from '@playwright/test'
import {
  api,
  shared,
  privateSpace,
  article,
  source,
  version,
  fixturePage,
} from './fixtures'

test('reader navigation is local, read-only and keyboard accessible in both languages and themes', async ({
  page,
}) => {
  await api(page)
  const errors: string[] = [],
    mutations: string[] = [],
    external: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('request', (request) => {
    if (request.method() !== 'GET') mutations.push(request.url())
    if (request.url().startsWith('https://')) external.push(request.url())
  })
  for (const language of ['en', 'it'])
    for (const theme of ['light', 'dark'])
      for (const width of [1440, 390]) {
        await page.addInitScript(
          ({ language, theme }) => {
            localStorage.setItem('c0-language', language)
            localStorage.setItem('c0-theme', theme)
          },
          { language, theme },
        )
        await page.setViewportSize({ width, height: 1000 })
        await page.goto(`/wiki/${article}?space_id=${shared}`)
        await expect(
          page.getByRole('button', {
            name:
              language === 'en'
                ? 'Knowledge space Shared'
                : 'Spazio di conoscenza Shared',
            exact: true,
          }),
        ).toBeVisible({ timeout: 15000 })
        await expect(page.locator('article')).toContainText('Final checks.')
        await expect(page.locator('article script,article img')).toHaveCount(0)
        await expect(page.locator('html')).toHaveAttribute('lang', language)
        if (process.env.CZERO_VISUAL_OUTPUT)
          await page.screenshot({
            path: `${process.env.CZERO_VISUAL_OUTPUT}/wiki-${language}-${theme}-${width}.png`,
            fullPage: true,
          })
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBe(true)
        await page.locator('.skip-link').focus()
        await page.keyboard.press('Enter')
        await expect(page.locator('#main')).toBeFocused()
        await expect(
          page.getByRole('button', {
            name: /Edit|Delete|Archive|Modifica|Elimina|Archivia/,
          }),
        ).toHaveCount(0)
      }
  expect(errors).toEqual([])
  expect(mutations).toEqual([])
  expect(external).toEqual([])
})

test('source replacement defaults to no original retention and retains revision guard', async ({
  page,
}) => {
  await api(page, 'editor')
  let uploadBody = ''
  await page.route('**/api/v1/sources/upload?**', async (route) => {
    uploadBody = route.request().postData() || ''
    expect(route.request().headers()['x-c0-csrf']).toBe('fixture-csrf')
    await route.fulfill({
      status: 202,
      json: { id: version, source_id: source, state: 'queued' },
    })
  })
  await page.goto(`/sources/${source}?space_id=${shared}`)
  await expect(page.locator('article')).toContainText(
    'Original published document.',
  )
  await page
    .getByRole('button', { name: 'Upload replacement', exact: true })
    .click()
  await expect(
    page.getByRole('checkbox', { name: 'Retain the original file' }),
  ).not.toBeChecked()
  await page.locator('input[type=file]').setInputFiles({
    name: 'replacement.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# Replacement evidence'),
  })
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Upload replacement', exact: true })
    .click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expect(uploadBody).toContain('name="retain_original"\r\n\r\nfalse')
  expect(uploadBody).toContain('name="expected_revision"\r\n\r\n3')
  expect(uploadBody).toContain(source)
  await expect(page.locator('article')).toContainText(
    'Original published document.',
  )
})

test('superseded evidence stays unavailable without requesting replacement text', async ({
  page,
}) => {
  await api(page)
  const reads: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/api/')) reads.push(request.url())
  })
  await page.route('**/chunks/expired/citation?**', (route) =>
    route.fulfill({ status: 410, json: { detail: 'content_superseded' } }),
  )
  await page.goto(`/evidence/expired?space_id=${shared}`)
  await expect(
    page.getByText(
      'This exact evidence has been superseded and is unavailable.',
    ),
  ).toBeVisible()
  expect(
    reads.some(
      (url) =>
        url.includes('source-documents') || url.includes('source-versions'),
    ),
  ).toBe(false)
})

test('late document response cannot restore content after switching spaces', async ({
  page,
}) => {
  await api(page)
  let release!: () => void
  const wait = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route(`**/api/v1/wiki/pages/${article}?**`, async (route) => {
    await wait
    await route.fulfill({
      json: {
        ...fixturePage,
        content: {
          body: 'OLD PRIVATE BODY',
          title: 'Old private body',
          number: 1,
        },
      },
    })
  })
  await page.goto(`/wiki/${article}?space_id=${shared}`)
  await expect(
    page.getByRole('button', { name: 'Knowledge space Shared' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Knowledge space Shared' }).click()
  await page.getByRole('option', { name: 'Protected' }).click()
  release()
  await expect(page).toHaveURL(new RegExp(privateSpace))
  await expect(page.getByText('OLD PRIVATE BODY')).toHaveCount(0)
})

test('closing key creation discards a late one-time secret', async ({
  page,
}) => {
  await api(page, 'admin')
  let release!: () => void
  let sent!: () => void
  let reads = 0
  const received = new Promise<void>((resolve) => {
    sent = resolve
  })
  const response = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/v1/api-keys', async (route) => {
    if (route.request().method() === 'GET') {
      reads++
      return route.fulfill({ json: { api_keys: [] } })
    }
    sent()
    await response
    await route.fulfill({
      status: 201,
      json: { key: 'fixture-secret-must-not-be-disclosed' },
    })
  })
  await page.goto('/account')
  await page
    .getByRole('button', { name: 'Create API key', exact: true })
    .click()
  const drawer = page.getByRole('dialog')
  await drawer
    .getByRole('textbox', { name: 'Name', exact: true })
    .fill('Cancelled disclosure')
  await drawer.getByRole('checkbox', { name: 'Write', exact: true }).check()
  await drawer.getByRole('checkbox', { name: 'Shared', exact: true }).check()
  await drawer
    .getByRole('button', { name: 'Create API key', exact: true })
    .click()
  await received
  await drawer.getByRole('button', { name: 'Close', exact: true }).click()
  release()
  await expect.poll(() => reads).toBeGreaterThan(1)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.locator('body')).not.toContainText(
    'fixture-secret-must-not-be-disclosed',
  )
  expect(
    await page.evaluate(() => Object.values(localStorage).join(' ')),
  ).not.toContain('fixture-secret')
  await page
    .getByRole('button', { name: 'Create API key', exact: true })
    .click()
  await expect(
    drawer.getByRole('textbox', { name: 'Name', exact: true }),
  ).toHaveValue('')
  await expect(
    drawer.getByRole('checkbox', { name: 'Write', exact: true }),
  ).not.toBeChecked()
  await expect(
    drawer.getByRole('checkbox', {
      name: 'Shared',
      exact: true,
    }),
  ).not.toBeChecked()
})

test('mobile navigation returns keyboard focus to its trigger', async ({
  page,
}) => {
  await api(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/wiki')
  const trigger = page.getByRole('button', { name: 'Navigation', exact: true })
  await trigger.click()
  await expect(
    page.getByRole('dialog').getByRole('link', { name: 'Home', exact: true }),
  ).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(trigger).toBeFocused()
})

test('an expired connection explains how to restart setup', async ({
  page,
}) => {
  await api(page)
  await page.route('**/oauth/connect/request', (route) =>
    route.fulfill({
      status: 410,
      json: { detail: 'connection_request_unavailable' },
    }),
  )
  await page.goto('/oauth/connect')
  await expect(page.getByRole('alert')).toContainText(
    'Start Connect again in your assistant',
  )
  await expect(
    page.getByRole('link', { name: 'Back to setup', exact: true }),
  ).toHaveAttribute('href', '/agents')
  await expect(page.locator('main')).not.toContainText(
    'evidence has been superseded',
  )
})

test('ambiguous exact evidence selectors never fetch current content', async ({
  page,
}) => {
  await api(page)
  const bodies: string[] = []
  page.on('request', (request) => {
    if (
      /\/api\/v1\/(wiki\/pages\/|source-documents\/|source-versions\/)/.test(
        request.url(),
      )
    )
      bodies.push(request.url())
  })
  for (const route of [
    `/wiki/${article}?revision=1&revision=2`,
    `/wiki/${article}?revision=`,
    `/sources/${source}?version=${version}&version=${version}`,
    `/sources/${source}?revision_id=${version}&version=${version}`,
  ]) {
    await page.goto(route)
    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page.getByRole('article')).toHaveCount(0)
  }
  expect(bodies).toEqual([])
})
