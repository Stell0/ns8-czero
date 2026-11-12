import { expect, test } from '@playwright/test'
import { api, privateSpace, shared } from './fixtures'

for (const theme of ['light', 'dark']) {
  for (const width of [390, 1280]) {
    test(`administrator changes space audience: ${theme} ${width}`, async ({
      page,
    }, testInfo) => {
      await page.setViewportSize({ width, height: 844 })
      await page.addInitScript(
        (value) => localStorage.setItem('c0-theme', value),
        theme,
      )
      await api(page, 'admin')
      let readable = false
      let revision = 3
      let saves = 0
      await page.route('**/api/v1/spaces?**', (route) =>
        route.fulfill({
          json: {
            spaces: [
              {
                id: shared,
                name: 'Shared',
                shared: true,
                readable_by_all: true,
                role: 'admin',
                revision: 1,
              },
              {
                id: privateSpace,
                name: 'Documentation',
                shared: false,
                readable_by_all: readable,
                role: 'admin',
                revision,
              },
            ],
          },
        }),
      )
      await page.route('**/access/accounts?**', (route) =>
        route.fulfill({ json: { accounts: [] } }),
      )
      await page.route(`**/spaces/${privateSpace}/grants?**`, (route) =>
        route.fulfill({ json: { grants: [] } }),
      )
      await page.route(`**/spaces/${privateSpace}/access`, (route) => {
        const body = route.request().postDataJSON()
        expect(body.expected_revision).toBe(revision)
        expect(body.idempotency_key).toBeTruthy()
        expect(route.request().headers()['x-c0-csrf']).toBe('fixture-csrf')
        readable = body.readable_by_all
        revision++
        saves++
        return route.fulfill({
          json: { id: privateSpace, readable_by_all: readable, revision },
        })
      })
      await page.goto(`/admin/spaces?space_id=${privateSpace}`)
      await page
        .getByRole('button', { name: /^Who can read/ })
        .last()
        .click()
      await page
        .getByRole('option', { name: 'All signed-in users', exact: true })
        .click()
      const save = page.getByRole('button', {
        name: 'Save audience',
        exact: true,
      })
      await save.focus()
      await save.press('Enter')
      await expect.poll(() => saves).toBe(1)
      await expect(
        page.getByText(
          'You can read this space because it is available to all signed-in users.',
        ),
      ).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath('audience.png') })
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true)
    })
  }
}
