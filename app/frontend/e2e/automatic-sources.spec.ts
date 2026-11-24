import { expect, test } from '@playwright/test'
import { api, shared } from './fixtures'

for (const language of ['en', 'it'])
  test(`automatic source corrections and retry ${language}`, async ({
    page,
  }) => {
    await api(page, 'editor')
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
    await page.addInitScript((language) => {
      localStorage.setItem('c0-language', language)
      localStorage.setItem('c0-theme', language === 'en' ? 'light' : 'dark')
    }, language)
    await page.setViewportSize({
      width: language === 'en' ? 1440 : 390,
      height: 1000,
    })
    const submissions: Record<string, unknown>[] = []
    await page.route('**/api/v1/automatic-sources**', async (route) => {
      if (route.request().method() === 'GET')
        return route.fulfill({ json: { definitions: [] } })
      expect(new URL(route.request().url()).searchParams.get('space_id')).toBe(
        shared,
      )
      expect(route.request().headers()['x-c0-csrf']).toBe('fixture-csrf')
      submissions.push(route.request().postDataJSON())
      if (submissions.length === 1)
        return route.fulfill({
          status: 422,
          json: {
            detail: 'invalid_automatic_source',
            reason: 'invalid_github_ref',
            field: 'config.ref',
            message: '<img src=x onerror=alert(1)>PRIVATE_REMOTE_BODY',
          },
        })
      return route.fulfill({ json: { id: shared, revision: 1 } })
    })
    const en = language === 'en'
    await page.goto(`/automatic-sources?space_id=${shared}`)
    await page
      .getByRole('button', {
        name: en ? 'Add automatic source' : 'Aggiungi fonte automatica',
        exact: true,
      })
      .click()
    const dialog = page.getByRole('dialog')
    await dialog
      .getByRole('button', { name: en ? /Source type/ : /Tipo di fonte/ })
      .click()
    await page.getByRole('option', { name: 'GitHub', exact: true }).click()
    await dialog
      .getByRole('textbox', { name: en ? 'Title' : 'Titolo', exact: true })
      .fill('Public documentation')
    const repositories = dialog.getByRole('textbox', {
      name: en
        ? 'Repositories (owner/repository_name)'
        : 'Repository (owner/repository_name)',
      exact: true,
    })
    const save = dialog.getByRole('button', {
      name: en ? 'Save configuration' : 'Salva configurazione',
      exact: true,
    })
    const preview = dialog.getByRole('button', {
      name: en ? 'Preview' : 'Anteprima',
      exact: true,
    })
    await repositories.fill('synthetic')
    await preview.click()
    await expect(repositories).toHaveAttribute('aria-invalid', 'true')
    await expect(
      dialog.getByText(
        en
          ? 'Enter 1–100 distinct repositories as owner/repository_name. An organization name alone is not supported.'
          : 'Inserisci da 1 a 100 repository distinti nel formato owner/repository_name. Il solo nome di un’organizzazione non è supportato.',
        { exact: true },
      ),
    ).toBeVisible()
    await save.click()
    expect(submissions).toHaveLength(0)
    await repositories.fill('synthetic/docs')
    const files = dialog.getByRole('checkbox', {
      name: en ? 'Text and code files' : 'File di testo e codice',
      exact: true,
    })
    await files.uncheck()
    await preview.click()
    await expect(dialog.getByRole('alert')).toContainText(
      en
        ? 'Select at least one GitHub content type'
        : 'Seleziona almeno un tipo di contenuto GitHub',
    )
    expect(submissions).toHaveLength(0)
    await files.check()
    await save.click()
    await expect(dialog.getByRole('alert')).toContainText(
      en ? 'Cannot save source' : 'Impossibile salvare la fonte',
    )
    const branch = dialog.getByRole('textbox', {
      name: en ? 'Branch or reference' : 'Branch o riferimento',
      exact: true,
    })
    await expect(branch).toHaveAttribute('aria-invalid', 'true')
    await expect(dialog).not.toContainText('PRIVATE_REMOTE_BODY')
    await expect(dialog.locator('img')).toHaveCount(0)
    await expect(dialog).not.toContainText('Cannot load content')
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    await branch.fill('main')
    await expect(dialog.getByRole('alert')).toHaveCount(0)
    await expect(branch).not.toHaveAttribute('aria-invalid', 'true')
    await save.focus()
    await page.keyboard.press('Enter')
    await expect(dialog).toHaveCount(0)
    expect(submissions).toHaveLength(2)
    expect(submissions[1]).toMatchObject({
      kind: 'github',
      enabled: false,
      config: {
        repositories: ['synthetic/docs'],
        include: ['files'],
        paths: ['README*', 'docs/*'],
        ref: 'main',
      },
    })
    expect(submissions[1].idempotency_key).not.toBe(
      submissions[0].idempotency_key,
    )
  })
