import { expect, test } from '@playwright/test'
import { api, shared, privateSpace } from './fixtures'
const schema = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    score: { type: 'integer' },
    notes: { type: 'string' },
    nested: {
      type: 'array',
      items: { type: 'object', properties: { text: { type: 'string' } } },
    },
  },
}
const definition = { name: 'fixture_records', label: 'Fixture records', schema }
for (const theme of ['light', 'dark'])
  test(`discovers records without Wiki pages and browses schema tables: ${theme}`, async ({
    page,
  }) => {
    await api(page)
    await page.addInitScript(
      (theme) => localStorage.setItem('c0-theme', theme),
      theme,
    )
    await page.route('**/api/v1/wiki/pages?**', (route) =>
      route.fulfill({ json: { pages: [] } }),
    )
    await page.route('**/api/v1/object-types?**', (route) => {
      expect(new URL(route.request().url()).searchParams.get('space_id')).toBe(
        shared,
      )
      return route.fulfill({ json: { types: [definition] } })
    })
    await page.route('**/api/v1/object-types/fixture_records', (route) =>
      route.fulfill({ json: definition }),
    )
    await page.route('**/api/v1/objects?**', (route) => {
      const params = new URL(route.request().url()).searchParams
      expect(params.get('space_id')).toBe(shared)
      const offset = Number(params.get('offset'))
      const count = offset ? 1 : 50
      return route.fulfill({
        json: {
          objects: Array.from({ length: count }, (_, i) => ({
            id: `record-${offset + i}`,
            type_name: definition.name,
            revision: 1,
            created_at: '2026-01-01',
            updated_at: '2026-01-01',
            tags: [],
            data: {
              title: `Row ${offset + i}`,
              score: i,
              notes: '<img src=x onerror=alert(1)>',
              nested: [{ text: 'Nested content' }],
            },
          })),
        },
      })
    })
    await page.goto(`/?space_id=${shared}`)
    await page
      .getByRole('link', { name: 'Fixture records', exact: true })
      .click()
    await expect(
      page.getByRole('grid', { name: 'Fixture records' }),
    ).toBeVisible()
    await page.getByRole('button', { name: 'Score', exact: true }).click()
    await expect(page).toHaveURL(/sort=score/)
    await page.getByRole('button', { name: 'Next', exact: true }).click()
    await expect(
      page.getByText('Row 50', { exact: true }).first(),
    ).toBeVisible()
    await page.goBack()
    await expect(page.getByText('Row 0', { exact: true }).first()).toBeVisible()
    const details = page.getByRole('button', {
      name: 'Details · record-0',
      exact: true,
    })
    await details.focus()
    await page.keyboard.press('Enter')
    await expect(
      page.getByText('Nested content', { exact: true }).first(),
    ).toBeVisible()
    await expect(page.locator('img')).toHaveCount(0)
    await page.getByRole('button', { name: 'Close', exact: true }).click()
    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({ path: `/tmp/c0-tables-${theme}-mobile.png` })
    await expect(
      page.getByText('Row 0', { exact: true }).first().first(),
    ).toBeVisible()
  })
test('clears a table when switching to an inaccessible space', async ({
  page,
}) => {
  await api(page)
  await page.route('**/api/v1/object-types/fixture_records', (route) =>
    route.fulfill({ json: definition }),
  )
  await page.route('**/api/v1/objects?**', (route) => {
    const allowed =
      new URL(route.request().url()).searchParams.get('space_id') === shared
    return route.fulfill(
      allowed
        ? {
            json: {
              objects: [
                {
                  id: 'private-record',
                  revision: 1,
                  tags: [],
                  data: { title: 'Original space only' },
                },
              ],
            },
          }
        : { status: 403, json: { detail: 'permission_denied' } },
    )
  })
  await page.goto(`/tables/fixture_records?space_id=${shared}`)
  await expect(
    page.getByText('Original space only', { exact: true }).first(),
  ).toBeVisible()
  await page.goto(`/tables/fixture_records?space_id=${privateSpace}`)
  await expect(
    page.getByText('Original space only', { exact: true }),
  ).toHaveCount(0)
})
