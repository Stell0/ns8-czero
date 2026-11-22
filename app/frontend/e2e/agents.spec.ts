import { expect, test, type Page } from '@playwright/test'
import { api, privateSpace } from './fixtures'

const mcp = 'https://c0.example.test/mcp'

async function mockConnection(page: Page) {
  await page.route('**/agents/connection.json', (route) =>
    route.fulfill({ json: { available: true, mcp_url: mcp, name: 'Demo C0' } }),
  )
}

test('signed-out users can find the setup route and skill for each assistant', async ({
  page,
}) => {
  await page.route('**/api/v1/me', (route) => route.fulfill({ status: 401 }))
  await mockConnection(page)
  await page.goto('/agents')
  await expect(
    page.getByRole('textbox', { name: 'MCP server URL' }),
  ).toHaveCount(0)
  await expect(page.getByText('Advanced setup and workflows')).toHaveCount(0)
  const routes = [
    [
      'ChatGPT',
      'https://chatgpt.com/plugins?directoryTab=personal',
      'c0-memory.skill',
    ],
    ['Claude', 'https://claude.ai/', 'c0-skill.zip'],
    ['Grok', 'https://grok.com/connectors', 'c0-skill.md'],
    ['Gemini', 'https://gemini.google.com/', 'c0-skill.md'],
  ]
  for (const [assistant, settings, skill] of routes) {
    const option = page.getByRole('radio', { name: assistant, exact: true })
    await option.focus()
    await page.keyboard.press('Space')
    await expect(option).toBeChecked()
    await expect(
      page.getByRole('link', { name: `Open ${assistant}`, exact: true }),
    ).toHaveAttribute('href', settings)
    await expect(
      page.getByRole('link', { name: 'Download skill', exact: true }),
    ).toHaveAttribute('href', `/agents/${skill}`)
    await expect(
      page.getByRole('textbox', { name: 'MCP server URL' }),
    ).toHaveValue(mcp)
    await expect(
      page.getByRole('textbox', { name: 'First question' }),
    ).toHaveValue(/List my knowledge spaces/)
  }
})

test('the first question binds the selected space and advanced setup is opt-in', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ colorScheme: 'dark' })
  await api(page)
  await mockConnection(page)
  const capabilityRequests: string[] = []
  await page.route('**/agents/capabilities.json', (route) => {
    capabilityRequests.push(route.request().url())
    return route.fulfill({
      json: { operations: [], guidance: { rules: [], workflows: [] } },
    })
  })
  await page.goto(`/agents?space_id=${privateSpace}`)
  await page.getByText('ChatGPT', { exact: true }).click()
  const prompt = page.getByRole('textbox', { name: 'First question' })
  await expect(prompt).toHaveValue(new RegExp(privateSpace))
  const packageField = page.getByRole('textbox', {
    name: 'Registered ChatGPT app ID',
  })
  await expect(packageField).toHaveCount(0)
  expect(capabilityRequests).toEqual([])
  const advanced = page.getByText('Advanced setup and workflows', {
    exact: true,
  })
  await advanced.focus()
  await page.keyboard.press('Enter')
  await expect(packageField).toBeVisible()
  await expect.poll(() => capabilityRequests.length).toBe(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    390,
  )
  await page.getByText('Claude', { exact: true }).click()
  await expect(packageField).toHaveCount(0)
})
