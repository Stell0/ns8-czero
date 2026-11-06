import { expect, test, type Page } from '@playwright/test'
import { api } from './fixtures'
const identity = 'https://client.example.test/client.json'
const callback = 'https://client.example.test/callback'
const descriptor = {
  client_id: identity,
  client_name: 'Grok fixture',
  redirect_uris: [callback],
  scope_ceiling: ['c0:read', 'c0:write'],
}
const digest = 'a'.repeat(64)
const client = {
  client_id: 'fixture-client',
  metadata_url: identity,
  client_name: descriptor.client_name,
  redirect_uris: [callback],
  allowed_scopes: ['c0:read'],
  enabled: true,
  revision: 5,
  metadata_digest: digest,
  review_required: false,
}
async function metadata(page: Page, existing = true) {
  await page.route('**/oauth/clients', (route) =>
    route.fulfill({ json: { clients: existing ? [client] : [] } }),
  )
  await page.route('**/oauth/cimd', (route) =>
    route.fulfill({
      json: { enabled: true, clients: existing ? [client] : [] },
    }),
  )
  await page.route('**/oauth/cimd/preview', (route) =>
    route.fulfill({ json: { descriptor, metadata_digest: digest } }),
  )
}
test('existing application loads its review automatically and unchanged approval preserves grants', async ({
  page,
}) => {
  await api(page, 'admin')
  await metadata(page)
  const writes: string[] = []
  page.on('request', (request) => {
    if (/oauth\/cimd\/clients/.test(request.url())) writes.push(request.url())
  })
  await page.goto('/admin/advanced')
  await page
    .getByRole('button', { name: 'Approve application', exact: true })
    .click()
  const dialog = page.getByRole('dialog')
  await expect(
    dialog.getByText(descriptor.client_name, { exact: true }),
  ).toBeVisible()
  await dialog
    .getByRole('button', { name: 'Approve application', exact: true })
    .click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('status')).toContainText(
    'No application permissions changed',
  )
  expect(writes).toEqual([])
})
test('changed approval saves the reviewed digest and revision and explains reconnecting', async ({
  page,
}) => {
  await api(page, 'admin')
  await metadata(page)
  let writes = 0
  await page.route('**/oauth/cimd/clients/fixture-client', async (route) => {
    writes++
    expect(route.request().method()).toBe('PUT')
    expect(route.request().headers()['x-c0-csrf']).toBe('fixture-csrf')
    expect(route.request().postDataJSON()).toEqual({
      metadata_digest: digest,
      allowed_scopes: ['c0:read', 'c0:write'],
      expected_revision: 5,
    })
    await route.fulfill({
      json: { ...client, revision: 6, allowed_scopes: ['c0:read', 'c0:write'] },
    })
  })
  await page.goto('/admin/advanced')
  await page
    .getByRole('button', { name: 'Approve application', exact: true })
    .click()
  const dialog = page.getByRole('dialog')
  await expect(
    dialog.getByText(descriptor.client_name, { exact: true }),
  ).toBeVisible()
  await dialog.getByRole('checkbox', { name: 'Write', exact: true }).check()
  await dialog
    .getByRole('button', { name: 'Approve application', exact: true })
    .press('Enter')
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('status')).toContainText(
    'Return to your assistant',
  )
  expect(writes).toBe(1)
})
async function connect(page: Page, role = 'admin') {
  await api(page, role)
  await metadata(page, false)
  await page.route('**/oauth/connect/request', (route) =>
    route.fulfill({
      json: {
        metadata_url: identity,
        callback,
        scopes: ['c0:read', 'c0:write', 'c0:admin'],
        approved: false,
        allowed_scopes: [],
        csrf_token: 'fixture-csrf',
      },
    }),
  )
}
test('administrator can approve and continue without opening Details', async ({
  page,
}) => {
  await connect(page)
  const writes: string[] = []
  await page.route('**/oauth/cimd/clients', async (route) => {
    writes.push('approve')
    expect(route.request().postDataJSON()).toEqual({
      metadata_url: identity,
      metadata_digest: digest,
      allowed_scopes: ['c0:read'],
    })
    await route.fulfill({ json: client })
  })
  await page.route('**/oauth/connect/continue', async (route) => {
    writes.push('continue')
    expect(route.request().postDataJSON()).toEqual({ scopes: ['c0:read'] })
    await route.fulfill({ json: { next: '/oauth/consent' } })
  })
  await page.route('**/oauth/consent/request', (route) =>
    route.fulfill({
      json: {
        client_name: descriptor.client_name,
        client_id: identity,
        callback,
        scopes: ['c0:read'],
        eligible_scopes: ['c0:read'],
        csrf_token: 'fixture-csrf',
      },
    }),
  )
  await page.goto('/oauth/connect')
  await expect(
    page.getByRole('heading', { name: descriptor.client_name }),
  ).toBeVisible()
  await expect(
    page.getByRole('checkbox', { name: 'Manage', exact: true }),
  ).toBeDisabled()
  await expect(
    page.getByRole('checkbox', { name: 'Write', exact: true }),
  ).not.toBeChecked()
  expect(writes).toEqual([])
  await page
    .getByRole('button', { name: 'Approve and continue', exact: true })
    .press('Enter')
  await expect(page).toHaveURL(/\/oauth\/consent$/)
  await expect(
    page.getByRole('button', { name: 'Authorize', exact: true }),
  ).toBeEnabled()
  expect(writes).toEqual(['approve', 'continue'])
})
test('ordinary user waits for approval and never fetches administrator metadata', async ({
  page,
}) => {
  await connect(page, 'reader')
  const adminRequests: string[] = []
  page.on('request', (req) => {
    if (/oauth\/cimd/.test(req.url())) adminRequests.push(req.url())
  })
  await page.goto('/oauth/connect')
  await expect(
    page.getByText('This connection needs administrator approval.', {
      exact: false,
    }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Authorize', exact: true }),
  ).toBeDisabled()
  expect(adminRequests).toEqual([])
})
for (const theme of ['light', 'dark']) {
  for (const width of [390, 1280]) {
    test(`consent layout and keyboard in ${theme} at ${width}`, async ({
      page,
    }) => {
      await page.emulateMedia({ colorScheme: theme as 'light' | 'dark' })
      await page.setViewportSize({ width, height: 844 })
      await api(page, 'admin')
      await page.route('**/oauth/consent/request', (route) =>
        route.fulfill({
          json: {
            client_name: 'Grok fixture',
            callback,
            scopes: ['c0:read', 'c0:write', 'c0:admin'],
            eligible_scopes: ['c0:read', 'c0:write', 'c0:admin'],
            csrf_token: 'fixture-csrf',
            background_supported: true,
            connection_idle_seconds: 2592000,
          },
        }),
      )
      await page.goto('/oauth/consent')
      const authorize = page.getByRole('button', {
        name: 'Authorize',
        exact: true,
      })
      await expect(authorize).toBeEnabled()
      await expect(page.getByRole('search')).toHaveCount(0)
      await expect(page.locator('[data-c0-navigation]')).toHaveCount(0)
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true)
      const boxes = await page
        .getByRole('checkbox')
        .evaluateAll((inputs) =>
          inputs.map((input) => input.getBoundingClientRect().toJSON()),
        )
      expect(boxes).toHaveLength(4)
      for (let i = 1; i < boxes.length; i++)
        expect(boxes[i].top).toBeGreaterThan(boxes[i - 1].bottom)
      await page.getByRole('checkbox', { name: 'Manage', exact: true }).focus()
      await page.keyboard.press('Tab')
      await expect(
        page.getByRole('checkbox', {
          name: 'Allow background access',
          exact: true,
        }),
      ).toBeFocused()
      await page.keyboard.press('Tab')
      await expect(page.locator('summary')).toBeFocused()
      await page.keyboard.press('Tab')
      await expect(authorize).toBeFocused()
    })
  }
}

test('invalid callback metadata never enables approval or advances the connection', async ({
  page,
}) => {
  await connect(page)
  await page.route('**/oauth/cimd/preview', (route) =>
    route.fulfill({
      json: {
        descriptor: {
          ...descriptor,
          redirect_uris: ['https://other.example.test/callback'],
        },
        metadata_digest: digest,
      },
    }),
  )
  const writes: string[] = []
  page.on('request', (request) => {
    if (/oauth\/(cimd\/clients|connect\/continue)/.test(request.url()))
      writes.push(request.url())
  })
  await page.goto('/oauth/connect')
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Approve and continue', exact: true }),
  ).toBeDisabled()
  expect(writes).toEqual([])
})

test('failed application save shows an error and never continues OAuth', async ({
  page,
}) => {
  await connect(page)
  await page.route('**/oauth/cimd/clients', (route) =>
    route.fulfill({ status: 409, json: { detail: 'private backend detail' } }),
  )
  let continued = false
  await page.route('**/oauth/connect/continue', (route) => {
    continued = true
    return route.fulfill({ json: {} })
  })
  await page.goto('/oauth/connect')
  await page
    .getByRole('button', { name: 'Approve and continue', exact: true })
    .click()
  await expect(page.getByRole('alert')).toContainText('This item changed')
  expect(continued).toBe(false)
  await expect(page.locator('body')).not.toContainText('private backend detail')
})
