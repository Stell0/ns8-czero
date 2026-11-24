import { expect, test } from '@playwright/test'
import { api, shared, source, version } from './fixtures'

test('replacement asks for the opening password and then for explicit extraction approval', async ({
  page,
}) => {
  await api(page, 'editor')
  let requests = 0
  await page.route('**/api/v1/sources/upload?**', async (route) => {
    const body = route.request().postData() || ''
    requests++
    expect(route.request().headers()['x-c0-csrf']).toBe('fixture-csrf')
    expect(body).toContain('name="expected_revision"\r\n\r\n3')
    expect(body).toContain('filename="restricted.pdf"')
    if (requests === 1) {
      expect(body).not.toContain('name="pdf_password"')
      await route.fulfill({
        status: 422,
        json: { detail: 'pdf_password_required' },
      })
    } else if (requests === 2) {
      expect(body).toContain('name="pdf_password"\r\n\r\nwrong')
      await route.fulfill({
        status: 422,
        json: { detail: 'pdf_password_incorrect' },
      })
    } else if (requests === 3) {
      expect(body).toContain('name="pdf_password"\r\n\r\nsynthetic-password')
      expect(body).not.toContain('name="pdf_approval_token"')
      await route.fulfill({
        status: 422,
        json: {
          detail: 'pdf_extraction_approval_required',
          approval_token: 'file-challenge',
        },
      })
    } else {
      expect(body).toContain('name="pdf_password"\r\n\r\nsynthetic-password')
      expect(body).toContain('name="pdf_approval_token"\r\n\r\nfile-challenge')
      await route.fulfill({
        status: 202,
        json: { id: version, source_id: source, state: 'queued' },
      })
    }
  })
  await page.goto(`/sources/${source}?space_id=${shared}`)
  await page
    .getByRole('button', { name: 'Upload replacement', exact: true })
    .click()
  const dialog = page.getByRole('dialog')
  await dialog.locator('input[type=file]').setInputFiles({
    name: 'restricted.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('Synthetic PDF'),
  })
  const submit = dialog.getByRole('button', {
    name: 'Upload replacement',
    exact: true,
  })
  await submit.click()
  const password = dialog.getByLabel('PDF password', { exact: true })
  await expect(password).toHaveAttribute('type', 'password')
  await expect(password).toBeFocused()
  await expect(submit).toBeDisabled()
  await password.fill('wrong')
  await submit.click()
  await expect(
    dialog.getByText('The password could not open this PDF. Try again.'),
  ).toBeVisible()
  await expect(password).toHaveValue('')
  await password.fill('synthetic-password')
  await submit.click()
  await expect(
    dialog.getByText(
      'People with Read access to Shared will be able to read the extracted text from restricted.pdf.',
      { exact: false },
    ),
  ).toBeVisible()
  await expect(submit).toBeDisabled()
  const approval = dialog.getByRole('checkbox', {
    name: 'I’m authorized to extract text from this PDF',
  })
  await expect(approval).not.toBeChecked()
  await approval.check()
  await submit.click()
  await expect(dialog).toHaveCount(0)
  expect(requests).toBe(4)
  await expect(page.locator('article')).toContainText(
    'Original published document.',
  )
})

test('a retained PDF can be reviewed without a password and cancellation queues nothing', async ({
  page,
}) => {
  await api(page, 'editor')
  await page.addInitScript(() => {
    localStorage.setItem('c0-language', 'it')
    localStorage.setItem('c0-theme', 'dark')
  })
  await page.setViewportSize({ width: 390, height: 800 })
  await page.route(`**/api/v1/sources/${source}/versions?**`, (route) =>
    route.fulfill({
      json: {
        versions: [
          {
            id: version,
            source_id: source,
            state: 'failed',
            generation: 2,
            filename: 'retained.pdf',
            original_present: true,
            error_code: 'encrypted_pdf',
          },
        ],
      },
    }),
  )
  let queued = 0
  await page.route(
    `**/api/v1/source-versions/${version}/pdf-retry?**`,
    async (route) => {
      const body = route.request().postDataJSON()
      if (!body.pdf_approval_token) {
        expect(body).toEqual({ expected_generation: 2 })
        await route.fulfill({
          status: 422,
          json: {
            detail: 'pdf_extraction_approval_required',
            approval_token: 'retained-file-challenge',
          },
        })
      } else {
        expect(body).toEqual({
          expected_generation: 2,
          pdf_approval_token: 'retained-file-challenge',
        })
        queued++
        await route.fulfill({
          status: 202,
          json: { id: version, state: 'queued' },
        })
      }
    },
  )
  await page.goto(`/sources/${source}?space_id=${shared}`)
  const review = page.getByRole('button', {
    name: 'Verifica il PDF e riprova',
    exact: true,
  })
  const dialog = page.getByRole('dialog', { name: 'Verifica il PDF e riprova' })
  const next = dialog.getByRole('button', { name: 'Continua', exact: true })
  const approval = dialog.getByRole('checkbox', {
    name: 'Ho l’autorizzazione a estrarre il testo da questo PDF',
  })
  await review.click()
  await next.click()
  await expect(
    dialog.getByText('retained.pdf', { exact: false }).first(),
  ).toBeVisible()
  await expect(approval).not.toBeChecked()
  await expect(next).toBeDisabled()
  await dialog.getByRole('button', { name: 'Annulla' }).click()
  await expect(dialog).toHaveCount(0)
  expect(queued).toBe(0)
  await review.click()
  await next.click()
  await approval.check()
  await next.click()
  await expect(dialog).toHaveCount(0)
  expect(queued).toBe(1)
})

test('selecting another PDF clears approval for the previous file', async ({
  page,
}) => {
  await api(page, 'editor')
  let attempts = 0
  await page.route('**/api/v1/sources/upload?**', async (route) => {
    const body = route.request().postData() || ''
    attempts++
    expect(body).not.toContain('name="pdf_approval_token"')
    if (attempts === 1) {
      await route.fulfill({
        status: 422,
        json: {
          detail: 'pdf_extraction_approval_required',
          approval_token: 'old-file-token',
        },
      })
    } else {
      expect(body).toContain('filename="new.pdf"')
      await route.fulfill({
        status: 202,
        json: { id: version, source_id: source, state: 'queued' },
      })
    }
  })
  await page.goto(`/sources/${source}?space_id=${shared}`)
  await page
    .getByRole('button', { name: 'Upload replacement', exact: true })
    .click()
  const dialog = page.getByRole('dialog')
  const file = dialog.locator('input[type=file]')
  const submit = dialog.getByRole('button', {
    name: 'Upload replacement',
    exact: true,
  })
  await file.setInputFiles({
    name: 'restricted.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('Restricted PDF'),
  })
  await submit.click()
  const approval = dialog.getByRole('checkbox', {
    name: 'I’m authorized to extract text from this PDF',
  })
  await approval.check()
  await file.setInputFiles({
    name: 'new.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('New PDF'),
  })
  await expect(approval).toHaveCount(0)
  await submit.click()
  await expect(dialog).toHaveCount(0)
  expect(attempts).toBe(2)
})
