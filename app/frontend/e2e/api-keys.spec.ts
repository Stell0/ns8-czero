import { expect, test } from '@playwright/test'
import { api, shared } from './fixtures'

for (const language of ['en', 'it'])
  for (const theme of ['light', 'dark'])
    for (const width of [1440, 390])
      test(`API key expiration ${language} ${theme} ${width}`, async ({
        page,
      }) => {
        await api(page)
        await page.addInitScript(
          ({ language, theme }) => {
            localStorage.setItem('c0-language', language)
            localStorage.setItem('c0-theme', theme)
          },
          { language, theme },
        )
        await page.setViewportSize({ width, height: 1000 })
        const requests: unknown[] = []
        await page.route('**/api/v1/api-keys', async (route) => {
          if (route.request().method() === 'POST') {
            requests.push(route.request().postDataJSON())
            return route.fulfill({
              status: 201,
              json: { key: 'fixture-secret' },
            })
          }
          return route.fulfill({ json: { api_keys: [] } })
        })
        const en = language === 'en'
        const create = en ? 'Create API key' : 'Crea chiave API'
        const never = en ? 'Never expires' : 'Nessuna scadenza'
        const invalid = en
          ? 'Enter a whole number from 1 to 365'
          : 'Inserisci un numero intero da 1 a 365'
        await page.goto('/account')
        await page.getByRole('button', { name: create, exact: true }).click()
        const drawer = page.getByRole('dialog')
        const days = drawer.getByRole('textbox', {
          name: en ? 'Lifetime in days' : 'Durata in giorni',
          exact: true,
        })
        const choice = drawer.getByRole('checkbox', {
          name: never,
          exact: true,
        })
        await expect(days).toHaveValue('90')
        await expect(choice).not.toBeChecked()
        await drawer
          .getByRole('textbox', { name: en ? 'Name' : 'Nome', exact: true })
          .fill('Workflow')
        await drawer
          .getByRole('checkbox', { name: 'Shared', exact: true })
          .check()
        for (const value of ['366', '', '1.5']) {
          await days.fill(value)
          await drawer
            .getByRole('button', { name: create, exact: true })
            .click()
          await expect(drawer.getByText(invalid, { exact: true })).toBeVisible()
          await expect(days).toHaveAttribute('aria-invalid', 'true')
          expect(requests).toHaveLength(0)
        }
        await days.focus()
        await page.keyboard.press('Tab')
        await expect(choice).toBeFocused()
        await page.keyboard.press('Space')
        await expect(days).toBeDisabled()
        await expect(drawer.getByText(invalid, { exact: true })).toHaveCount(0)
        await page.keyboard.press('Space')
        await expect(days).toBeEnabled()
        await days.fill('365')
        await choice.check()
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBe(true)
        await drawer.getByRole('button', { name: create, exact: true }).click()
        await expect.poll(() => requests.length).toBe(1)
        expect(requests[0]).toEqual({
          name: 'Workflow',
          lifetime_days: null,
          scopes: ['c0:read'],
          space_ids: [shared],
        })
        await drawer
          .getByRole('button', {
            name: en ? 'I saved the key' : 'Ho salvato la chiave',
            exact: true,
          })
          .click()
        await expect(drawer).toHaveCount(0)
        await page.getByRole('button', { name: create, exact: true }).click()
        await expect(days).toHaveValue('90')
        await expect(choice).not.toBeChecked()
        await drawer
          .getByRole('textbox', { name: en ? 'Name' : 'Nome', exact: true })
          .fill('Expiring')
        await drawer
          .getByRole('checkbox', { name: 'Shared', exact: true })
          .check()
        await days.fill('365')
        await drawer.getByRole('button', { name: create, exact: true }).click()
        await expect.poll(() => requests.length).toBe(2)
        expect(requests[1]).toEqual({
          name: 'Expiring',
          lifetime_days: 365,
          scopes: ['c0:read'],
          space_ids: [shared],
        })
      })
