import { beforeEach, describe, expect, it, vi } from 'vitest'
const transport = vi.hoisted(() => ({ request: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({
  default: {
    create: () => transport,
    isAxiosError: (error: { response?: unknown }) => !!error.response,
  },
}))
import {
  AccessBoundary,
  ApiError,
  StaleResponse,
  apiURL,
  bindContext,
  boundary,
  endSession,
  request,
} from '../src/api/client'
const space = '11111111-1111-4111-8111-111111111111'
beforeEach(() => {
  vi.clearAllMocks()
  boundary.invalidate()
  bindContext(() => ({ ready: true, csrf: 'fixture-csrf', space }))
})

describe('access boundary', () => {
  it('aborts and discards a late response even when the transport ignores abort', async () => {
    const guard = new AccessBoundary()
    let settle!: (value: string) => void
    let signal!: AbortSignal
    const pending = guard.run((s) => {
      signal = s
      return new Promise<string>((resolve) => {
        settle = resolve
      })
    })
    const rejected = expect(pending).rejects.toBeInstanceOf(StaleResponse)
    guard.invalidate()
    settle('private old account body')
    expect(signal.aborted).toBe(true)
    await rejected
  })
  it('never falls back from an unavailable selected space', async () => {
    bindContext(() => ({ ready: false, space }))
    expect(() => apiURL('wiki/pages')).toThrow(ApiError)
    await expect(request('wiki/pages')).rejects.toBeInstanceOf(ApiError)
    expect(transport.request).not.toHaveBeenCalled()
  })
  it('preserves selection and CSRF without using browser storage', async () => {
    transport.request.mockResolvedValue({ data: { id: 'saved' } })
    await request('sources/upload', { method: 'POST', data: new FormData() })
    expect(transport.request.mock.calls[0][0].url).toBe(
      `/api/v1/sources/upload?space_id=${space}`,
    )
    expect(transport.request.mock.calls[0][0].headers['X-C0-CSRF']).toBe(
      'fixture-csrf',
    )
    expect(localStorage.length).toBe(0)
  })
  it('clears protected observers on access loss', async () => {
    const cleared = vi.fn(),
      release = boundary.onClear(cleared)
    transport.request.mockRejectedValue({
      response: { status: 403, data: { detail: 'forbidden' } },
    })
    await expect(request('wiki/pages')).rejects.toMatchObject({ status: 403 })
    expect(cleared).toHaveBeenCalledOnce()
    release()
  })
  it('returns supersession without a current-generation fallback request', async () => {
    transport.request.mockRejectedValue({
      response: { status: 410, data: { detail: 'content_superseded' } },
    })
    await expect(request('chunks/expired/citation')).rejects.toMatchObject({
      status: 410,
      code: 'content_superseded',
    })
    expect(transport.request).toHaveBeenCalledOnce()
  })
  it('clears protected state before logout finishes and retains only its CSRF snapshot', async () => {
    const cleared = vi.fn(),
      release = boundary.onClear(cleared)
    transport.post.mockResolvedValue({ data: { logout_url: '/signed-out' } })
    const pending = endSession()
    expect(cleared).toHaveBeenCalledOnce()
    expect(transport.post).toHaveBeenCalledWith('/auth/logout', null, {
      headers: { 'X-C0-CSRF': 'fixture-csrf' },
    })
    await expect(pending).resolves.toEqual({ logout_url: '/signed-out' })
    release()
  })
})

it('ignores a late denial from an earlier account without clearing the new account', async () => {
  let reject!: (error: unknown) => void
  transport.request.mockImplementation(
    () =>
      new Promise((_, fail) => {
        reject = fail
      }),
  )
  const pending = request('wiki/pages')
  const rejected = expect(pending).rejects.toBeInstanceOf(StaleResponse)
  boundary.invalidate()
  const epoch = boundary.epoch
  reject({ response: { status: 403, data: { detail: 'forbidden' } } })
  await rejected
  expect(boundary.epoch).toBe(epoch)
})

it('does not redirect a new session when an old logout finishes', async () => {
  let finish!: (value: unknown) => void
  transport.post.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const pending = endSession()
  const rejected = expect(pending).rejects.toBeInstanceOf(StaleResponse)
  boundary.invalidate()
  finish({ data: { logout_url: '/old-provider-logout' } })
  await rejected
})
