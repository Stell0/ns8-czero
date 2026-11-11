import { expect, test, type Page } from '@playwright/test'
import { api } from './fixtures'
const person = {
  id: 'person',
  username: '<img> Person',
  role: 'reader',
  blocked: false,
  is_owner: false,
  access_revision: 3,
}
const application = {
  id: 'request-id',
  kind: 'request',
  client_name: '<script> Application',
  client_id: 'client-id',
  scopes: ['c0:read'],
  status: 'pending',
}
const descriptor = {
  client_name: '<img> Reviewed application',
  client_id: 'https://client.example.test/client.json',
  redirect_uris: ['https://client.example.test/callback'],
  scope_ceiling: ['c0:read'],
}
const digest = 'a'.repeat(64)
const reviewRequest = {
  callback: 'http://localhost:53123/callback',
  scopes: ['c0:read'],
}
async function access(page: Page) {
  await api(page, 'admin')
  await page.route('**/access/workspace?**', (route) =>
    route.fulfill({ json: { accounts: [person], has_more: false } }),
  )
  await page.route('**/access/accounts/person/applications?**', (route) =>
    route.fulfill({ json: { applications: [application], has_more: false } }),
  )
}

test('long client names and details stay within the phone layout', async ({
  page,
}) => {
  await api(page, 'admin')
  const name = 'client' + 'abcdef0123456789'.repeat(10)
  await page.route('**/oauth/clients', (route) =>
    route.fulfill({
      json: {
        clients: [
          {
            client_id: 'fixture-client',
            client_name: name,
            allowed_scopes: ['c0:read'],
            redirect_uris: ['https://client.example.test/callback'],
            enabled: true,
            revision: 1,
          },
        ],
      },
    }),
  )
  await page.route('**/oauth/cimd', (route) =>
    route.fulfill({ json: { clients: [], enabled: false } }),
  )
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/admin/advanced')
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
  await page.locator('summary').click()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
})

test('Reader and Editor never request administrator lists or expose controls', async ({
  page,
}) => {
  for (const role of ['reader', 'editor']) {
    await page.unrouteAll()
    await api(page, role)
    const reads: string[] = []
    const observe = (request: import('@playwright/test').Request) => {
      if (
        /\/api\/v1\/(access|oauth\/clients|oauth\/cimd|jobs|schedules)/.test(
          request.url(),
        )
      )
        reads.push(request.url())
    }
    page.on('request', observe)
    for (const path of [
      '/admin',
      '/admin/advanced',
      '/admin/work',
      '/admin/spaces',
    ]) {
      await page.goto(path)
      await expect(
        page.getByText('Sign in or choose a space you can access.'),
      ).toBeVisible()
      await expect(
        page.getByRole('button', { name: /Approve|Create|Save access/ }),
      ).toHaveCount(0)
    }
    expect(reads).toEqual([])
    page.off('request', observe)
  }
})

test('role changes preserve expected revision and CSRF, suppress duplicate writes and show a safe conflict', async ({
  page,
}) => {
  await access(page)
  let finish!: () => void
  const held = new Promise<void>((resolve) => {
    finish = resolve
  })
  let writes = 0
  await page.route('**/access/accounts/person', async (route) => {
    writes++
    expect(route.request().postDataJSON()).toEqual({
      role: 'editor',
      expected_revision: 3,
    })
    expect(route.request().headers()['x-c0-csrf']).toBe('fixture-csrf')
    await held
    await route.fulfill({
      status: 409,
      json: { detail: 'private conflict details' },
    })
  })
  await page.goto('/admin')
  await expect(
    page.getByRole('gridcell', { name: person.username, exact: true }),
  ).toBeVisible()
  await expect(page.locator('main img,main script')).toHaveCount(0)
  await page
    .getByRole('button', { name: 'Change permissions', exact: true })
    .click()
  const modal = page.getByRole('dialog')
  await modal.getByRole('button', { name: 'Permission' }).click()
  await page.getByRole('option', { name: 'Write', exact: true }).click()
  const save = modal.getByRole('button', { name: 'Save', exact: true })
  await save.press('Enter')
  await expect(save).toBeDisabled()
  finish()
  await expect(
    modal.getByText(
      'This item changed. Reload its current state before trying again.',
    ),
  ).toBeVisible()
  expect(writes).toBe(1)
  expect(await page.locator('body').innerText()).not.toContain(
    'private conflict details',
  )
})

test('approval respects metadata ceiling and unchanged permissions preserve existing connections', async ({
  page,
}) => {
  await access(page)
  await page.route('**/access/requests/request-id/preview', (route) =>
    route.fulfill({
      json: {
        descriptor,
        request: reviewRequest,
        metadata_digest: digest,
        client: {
          client_id: 'client-id',
          revision: 2,
          enabled: true,
          review_required: false,
          metadata_digest: digest,
          allowed_scopes: ['c0:read'],
        },
      },
    }),
  )
  const writes: string[] = []
  page.on('request', (req) => {
    if (req.method() !== 'GET') writes.push(req.url())
  })
  await page.goto('/admin')
  await page
    .getByRole('button', { name: 'Approve application', exact: true })
    .click()
  const modal = page.getByRole('dialog')
  await expect(
    modal.getByRole('checkbox', { name: 'Read', exact: true }),
  ).toBeChecked()
  for (const name of ['Write', 'Manage']) {
    await expect(
      modal.getByRole('checkbox', { name, exact: true }),
    ).not.toBeChecked()
    await expect(
      modal.getByRole('checkbox', { name, exact: true }),
    ).toBeDisabled()
  }
  await modal
    .getByRole('button', { name: 'Approve application', exact: true })
    .click()
  await expect(
    page.getByText(
      'No application permissions changed. Existing connections remain active.',
    ),
  ).toBeVisible()
  expect(writes.length).toBe(1)
  expect(writes[0]).toContain('/preview')
})

test('application approval remains open until the save completes', async ({
  page,
}) => {
  await access(page)
  await page.route('**/access/requests/request-id/preview', (route) =>
    route.fulfill({
      json: {
        descriptor,
        request: reviewRequest,
        metadata_digest: digest,
        client: null,
      },
    }),
  )
  let finish!: () => void
  const held = new Promise<void>((resolve) => {
    finish = resolve
  })
  let started = false
  await page.route('**/access/requests/request-id/approve', async (route) => {
    started = true
    expect(route.request().postDataJSON()).toEqual({
      metadata_digest: digest,
      allowed_scopes: ['c0:read'],
      client_id: null,
      expected_revision: null,
    })
    await held
    await route.fulfill({ json: {} })
  })
  await page.goto('/admin')
  await page
    .getByRole('button', { name: 'Approve application', exact: true })
    .click()
  const modal = page.getByRole('dialog')
  const save = modal.getByRole('button', {
    name: 'Approve application',
    exact: true,
  })
  await save.click()
  await expect.poll(() => started).toBe(true)
  await expect(modal).toHaveCount(1)
  await expect(save).toBeVisible()
  await expect(save).toBeDisabled()
  finish()
  await expect(modal).toHaveCount(0)
})

for (const theme of ['light', 'dark']) {
  for (const width of [390, 1280]) {
    test(`native approval shows the requested callback and bounds permissions: ${theme} ${width}`, async ({
      page,
    }) => {
      await access(page)
      await page.setViewportSize({ width, height: 900 })
      await page.addInitScript(
        (theme) => localStorage.setItem('c0-theme', theme),
        theme,
      )
      await page.route('**/access/requests/request-id/preview', (route) =>
        route.fulfill({
          json: {
            descriptor: {
              ...descriptor,
              redirect_uris: ['http://localhost/callback'],
              scope_ceiling: null,
            },
            request: reviewRequest,
            metadata_digest: digest,
            client: null,
          },
        }),
      )
      let approved = false
      await page.route(
        '**/access/requests/request-id/approve',
        async (route) => {
          expect(route.request().postDataJSON()).toEqual({
            metadata_digest: digest,
            allowed_scopes: ['c0:read'],
            client_id: null,
            expected_revision: null,
          })
          approved = true
          await route.fulfill({ json: {} })
        },
      )
      await page.goto('/admin')
      await page
        .getByRole('button', { name: 'Approve application', exact: true })
        .click()
      const modal = page.getByRole('dialog')
      await expect(
        modal.getByText('Callback: ' + reviewRequest.callback, { exact: true }),
      ).toBeVisible()
      await expect(
        modal.getByRole('checkbox', { name: 'Read', exact: true }),
      ).toBeChecked()
      for (const name of ['Write', 'Manage']) {
        await expect(
          modal.getByRole('checkbox', { name, exact: true }),
        ).not.toBeChecked()
        await expect(
          modal.getByRole('checkbox', { name, exact: true }),
        ).toBeDisabled()
      }
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true)
      await expect(page.locator('html')).toHaveClass(
        theme === 'dark' ? /dark/ : /^(?!.*dark)/,
      )
      await page.screenshot({
        path: test.info().outputPath('approval.png'),
        animations: 'disabled',
      })
      const read = modal.getByRole('checkbox', { name: 'Read', exact: true })
      await page.keyboard.press('Tab')
      for (let step = 0; step < 4; step++) {
        if (
          await read.evaluate((element) => element === document.activeElement)
        )
          break
        await page.keyboard.press('Tab')
      }
      await expect(read).toBeFocused()
      await page.keyboard.press('Tab')
      await expect(
        modal.getByRole('button', { name: 'Approve application', exact: true }),
      ).toBeFocused()
      await page.keyboard.press('Tab')
      await expect(
        modal.getByRole('button', { name: 'Cancel', exact: true }),
      ).toBeFocused()
      await page.keyboard.press('Shift+Tab')
      await page.keyboard.press('Enter')
      await expect(modal).not.toBeVisible()
      expect(approved).toBe(true)
    })
  }
}

test('approval preserves existing application permissions for a narrower request', async ({
  page,
}) => {
  await access(page)
  await page.route('**/access/requests/request-id/preview', (route) =>
    route.fulfill({
      json: {
        descriptor: { ...descriptor, scope_ceiling: null },
        request: reviewRequest,
        metadata_digest: digest,
        client: {
          client_id: 'client-id',
          revision: 2,
          enabled: true,
          review_required: false,
          metadata_digest: digest,
          allowed_scopes: ['c0:read', 'c0:write'],
        },
      },
    }),
  )
  await page.goto('/admin')
  await page
    .getByRole('button', { name: 'Approve application', exact: true })
    .click()
  const modal = page.getByRole('dialog')
  for (const name of ['Read', 'Write']) {
    await expect(
      modal.getByRole('checkbox', { name, exact: true }),
    ).toBeChecked()
    await expect(
      modal.getByRole('checkbox', { name, exact: true }),
    ).toBeEnabled()
  }
  await expect(
    modal.getByRole('checkbox', { name: 'Manage', exact: true }),
  ).not.toBeChecked()
  await expect(
    modal.getByRole('checkbox', { name: 'Manage', exact: true }),
  ).toBeDisabled()
})

test('closing a metadata preview cannot populate a newly opened client form', async ({
  page,
}) => {
  await api(page, 'admin')
  await page.route('**/oauth/clients', (route) =>
    route.fulfill({ json: { clients: [] } }),
  )
  await page.route('**/oauth/cimd', (route) =>
    route.fulfill({ json: { enabled: true, clients: [] } }),
  )
  let finish!: () => void
  const held = new Promise<void>((resolve) => {
    finish = resolve
  })
  let started = false
  await page.route('**/oauth/cimd/preview', async (route) => {
    started = true
    await held
    await route.fulfill({ json: { descriptor, metadata_digest: digest } })
  })
  await page.goto('/admin/advanced')
  await page
    .getByRole('button', { name: 'Register client', exact: true })
    .click()
  let dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'Clients', exact: false }).click()
  await page.getByRole('option', { name: 'HTTPS', exact: true }).click()
  await dialog
    .getByRole('textbox', { name: 'Client metadata URL', exact: true })
    .fill(descriptor.client_id)
  await dialog
    .getByRole('button', { name: 'Load application', exact: true })
    .click()
  await expect.poll(() => started).toBe(true)
  await dialog.getByRole('button', { name: 'Close', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page
    .getByRole('button', { name: 'Register client', exact: true })
    .click()
  finish()
  dialog = page.getByRole('dialog')
  await expect(
    dialog.getByRole('textbox', { name: 'Name', exact: true }),
  ).toBeVisible()
  await expect(
    dialog.getByRole('checkbox', { name: 'Read', exact: true }),
  ).toBeChecked()
  await expect(
    dialog.getByRole('checkbox', { name: 'Manage', exact: true }),
  ).not.toBeChecked()
  await expect(
    dialog.getByText(descriptor.client_name, { exact: false }),
  ).toHaveCount(0)
})
