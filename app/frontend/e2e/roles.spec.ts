import { expect, test } from '@playwright/test'
import { api } from './fixtures'

for (const language of ['en', 'it'] as const) {
  for (const theme of ['light', 'dark']) {
    for (const width of [390, 1280]) {
      test(`cumulative roles preserve values and independent scopes: ${language} ${theme} ${width}`, async ({
        page,
      }, testInfo) => {
        const text =
          language === 'it'
            ? {
                edit: 'Modifica permessi',
                permission: 'Permesso',
                save: 'Salva',
                approve: 'Approva applicazione',
                labels: [
                  'Lettura e scrittura',
                  'Lettura, scrittura e gestione',
                  'Lettura',
                ],
                scopes: ['Lettura', 'Scrittura', 'Gestione'],
              }
            : {
                edit: 'Change permissions',
                permission: 'Permission',
                save: 'Save',
                approve: 'Approve application',
                labels: ['Read and write', 'Read, write and manage', 'Read'],
                scopes: ['Read', 'Write', 'Manage'],
              }
        await page.setViewportSize({ width, height: 844 })
        await page.emulateMedia({ reducedMotion: 'reduce' })
        await page.addInitScript(
          ({ language, theme }) => {
            localStorage.setItem('c0-language', language)
            localStorage.setItem('c0-theme', theme)
          },
          { language, theme },
        )
        await api(page, 'admin')
        let person = {
          id: 'person',
          username: 'Alice',
          role: 'reader',
          blocked: false,
          is_owner: false,
          access_revision: 3,
        }
        await page.route('**/access/workspace?**', (route) =>
          route.fulfill({ json: { accounts: [person], has_more: false } }),
        )
        await page.route('**/access/accounts/person/applications?**', (route) =>
          route.fulfill({
            json: {
              applications: [
                {
                  id: 'request-id',
                  kind: 'request',
                  client_name: 'Application',
                  client_id: 'client-id',
                  scopes: ['c0:read'],
                  status: 'pending',
                },
              ],
              has_more: false,
            },
          }),
        )
        const writes: string[] = []
        await page.route('**/access/accounts/person', async (route) => {
          const payload = route.request().postDataJSON()
          expect(payload.expected_revision).toBe(person.access_revision)
          expect(route.request().headers()['x-c0-csrf']).toBe('fixture-csrf')
          writes.push(payload.role)
          person = {
            ...person,
            role: payload.role,
            access_revision: person.access_revision + 1,
          }
          await route.fulfill({ json: { account: person } })
        })
        await page.route('**/access/requests/request-id/preview', (route) =>
          route.fulfill({
            json: {
              descriptor: {
                client_name: 'Application',
                client_id: 'https://client.example.test/client.json',
                redirect_uris: ['http://localhost/callback'],
                scope_ceiling: ['c0:read', 'c0:write', 'c0:admin'],
              },
              request: {
                callback: 'http://localhost:53123/callback',
                scopes: ['c0:read'],
              },
              metadata_digest: 'a'.repeat(64),
              client: null,
            },
          }),
        )
        await page.goto('/admin')
        const row = page.locator('[data-account-id="person"]')
        for (const label of text.labels) {
          await row
            .getByRole('button', { name: text.edit, exact: true })
            .click()
          const modal = page.getByRole('dialog')
          await modal
            .getByRole('button', { name: new RegExp(`^${text.permission}\\b`) })
            .click()
          await page.getByRole('option', { name: label, exact: true }).click()
          const save = modal.getByRole('button', {
            name: text.save,
            exact: true,
          })
          await save.focus()
          await expect(save).toBeFocused()
          await save.press('Enter')
          await expect(modal).toBeHidden()
          await expect(row.getByRole('gridcell').nth(1)).toContainText(label)
          if (label === text.labels[1])
            await page.screenshot({
              path: testInfo.outputPath('roles.png'),
              animations: 'disabled',
            })
          expect(
            await page.evaluate(
              () => document.documentElement.scrollWidth <= innerWidth,
            ),
          ).toBe(true)
        }
        expect(writes).toEqual(['editor', 'admin', 'reader'])
        await page
          .getByRole('button', { name: text.approve, exact: true })
          .click()
        const modal = page.getByRole('dialog')
        await expect(
          modal.getByRole('checkbox', { name: text.scopes[0], exact: true }),
        ).toBeChecked()
        for (const name of text.scopes.slice(1)) {
          await expect(
            modal.getByRole('checkbox', { name, exact: true }),
          ).not.toBeChecked()
          await expect(
            modal.getByRole('checkbox', { name, exact: true }),
          ).toBeDisabled()
        }
      })
    }
  }
}
