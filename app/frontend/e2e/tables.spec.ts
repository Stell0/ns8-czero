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
    await page
      .getByRole('button', { name: 'Filter field All records', exact: true })
      .click()
    await page.getByRole('option', { name: 'Score', exact: true }).click()
    const filterValue = page.getByRole('textbox', {
      name: 'Exact value (booleans: true or false)',
      exact: true,
    })
    await filterValue.fill('3')
    await page
      .getByRole('button', { name: 'Apply filters', exact: true })
      .click()
    await expect(page).toHaveURL(
      (url) => JSON.parse(url.searchParams.get('where') || '{}').score === 3,
    )
    await page
      .getByRole('button', { name: 'Reset filters', exact: true })
      .click()
    await expect(filterValue).toHaveValue('')
    await expect(page).toHaveURL((url) => !url.searchParams.has('where'))
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
    await expect(details).toHaveText('Details')
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

test('can return from an empty final collection page', async ({ page }) => {
  await api(page)
  await page.route('**/api/v1/object-types?**', (route) => {
    const offset = new URL(route.request().url()).searchParams.get('offset')
    return route.fulfill({
      json: {
        types:
          offset === '0'
            ? Array.from({ length: 50 }, (_, index) => ({
                ...definition,
                name: `fixture_${index}`,
                label: `Collection ${index}`,
              }))
            : [],
      },
    })
  })
  await page.goto(`/tables?space_id=${shared}`)
  await page.getByRole('button', { name: 'Next', exact: true }).click()
  await expect(page.getByText('No items found', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Previous', exact: true }).click()
  await expect(
    page.getByRole('link', { name: 'Collection 0', exact: true }),
  ).toBeVisible()
})

test('shows data columns for a schema containing only nested fields', async ({
  page,
}) => {
  await api(page)
  await page.route('**/api/v1/object-types/nested_only', (route) =>
    route.fulfill({
      json: {
        name: 'nested_only',
        label: 'Nested records',
        schema: {
          type: 'object',
          properties: {
            nested: {
              type: 'object',
              properties: { label: { type: 'string' } },
            },
          },
        },
      },
    }),
  )
  await page.route('**/api/v1/objects?**', (route) =>
    route.fulfill({
      json: {
        objects: [
          {
            id: 'nested-1',
            revision: 1,
            tags: [],
            data: { nested: { label: 'Nested only record' } },
          },
        ],
      },
    }),
  )
  await page.goto(`/tables/nested_only?space_id=${shared}`)
  await expect(
    page.getByRole('columnheader', { name: 'Nested', exact: true }),
  ).toBeVisible()
  await page.getByText('Object', { exact: true }).click()
  await expect(
    page.getByText('Nested only record', { exact: true }),
  ).toBeVisible()
})
