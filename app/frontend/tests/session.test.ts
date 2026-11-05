import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
const transport = vi.hoisted(() => ({ request: vi.fn() }))
vi.mock('axios', () => ({
  default: { create: () => transport, isAxiosError: () => false },
}))
import { useSession } from '../src/stores/session'
const shared = {
  id: '11111111-1111-4111-8111-111111111111',
  name: 'Shared',
  shared: true,
  role: 'reader',
  revision: 1,
}
const protectedSpace = {
  ...shared,
  id: '22222222-2222-4222-8222-222222222222',
  name: 'Private',
  shared: false,
}
beforeEach(() => {
  setActivePinia(createPinia())
  transport.request.mockImplementation(async ({ url }: { url: string }) => ({
    data: url.includes('/me')
      ? {
          id: 'account-a',
          username: 'Alice',
          role: 'reader',
          csrf_token: 'fixture-csrf',
        }
      : { spaces: [shared] },
  }))
})
it('does not silently choose Shared when protected access is denied', async () => {
  const session = useSession()
  await session.load(protectedSpace.id)
  expect(session.ready).toBe(false)
  expect(session.space).toBeUndefined()
  expect(session.error).toMatchObject({ status: 403 })
})
it('rejects ambiguous space selectors before sending any request', async () => {
  transport.request.mockClear()
  const session = useSession()
  await session.load([shared.id, protectedSpace.id])
  await session.load() // Reload must retain the invalid explicit selector.
  expect(session.ready).toBe(false)
  expect(transport.request).not.toHaveBeenCalled()
})
it('allows Reader navigation without loading administrator data', async () => {
  const session = useSession()
  await session.load(null)
  expect(session.ready).toBe(true)
  expect(session.canWrite).toBe(false)
  expect(session.isAdmin).toBe(false)
  expect(
    transport.request.mock.calls.every(
      ([config]) => !config.url.includes('access/accounts'),
    ),
  ).toBe(true)
})
