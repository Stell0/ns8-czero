import axios, { type AxiosRequestConfig } from 'axios'

export class ApiError extends Error {
  constructor(
    public status: number,
    public code = '',
  ) {
    super('C0 request failed')
  }
}

export class StaleResponse extends Error {}

// An aborted request can still settle. The epoch also guards parsed responses.
export class AccessBoundary {
  epoch = 0
  private controllers = new Set<AbortController>()
  private listeners = new Set<() => void>()
  invalidate() {
    this.epoch++
    for (const controller of this.controllers) controller.abort()
    this.controllers.clear()
    for (const listener of this.listeners) listener()
  }
  onClear(listener: () => void) {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }
  async run<T>(operation: (signal: AbortSignal) => Promise<T>) {
    const epoch = this.epoch
    const controller = new AbortController()
    this.controllers.add(controller)
    try {
      const value = await operation(controller.signal)
      if (epoch !== this.epoch) throw new StaleResponse()
      return value
    } catch (error) {
      if (
        epoch !== this.epoch &&
        !(error instanceof ApiError && [401, 403].includes(error.status))
      )
        throw new StaleResponse()
      throw error
    } finally {
      this.controllers.delete(controller)
    }
  }
}

export const boundary = new AccessBoundary()
export const basePath = new URL(document.baseURI).pathname.replace(/\/$/, '')
export const localURL = (path: string) =>
  `${basePath}/${path.replace(/^\//, '')}`
const http = axios.create({
  withCredentials: true,
  headers: { 'Cache-Control': 'no-cache' },
})
let context: () => { csrf?: string; space?: string; ready: boolean } = () => ({
  ready: false,
})
export function bindContext(value: typeof context) {
  context = value
}

export function apiURL(path: string, scoped = true) {
  const url = new URL(localURL(`api/v1/${path}`), location.origin)
  if (scoped) {
    const current = context()
    if (!current.ready || !current.space)
      throw new ApiError(403, 'space_unavailable')
    url.searchParams.set('space_id', current.space)
  }
  return url.pathname + url.search
}

export async function request<T>(
  path: string,
  options: AxiosRequestConfig = {},
  scoped = true,
): Promise<T> {
  const epoch = boundary.epoch
  return boundary.run(async (signal) => {
    const method = (options.method || 'GET').toUpperCase()
    const csrf = context().csrf
    if (method !== 'GET' && !csrf) throw new ApiError(403)
    try {
      const response = await http.request<T>({
        ...options,
        url: path.startsWith('/') ? localURL(path) : apiURL(path, scoped),
        signal,
        headers: {
          ...options.headers,
          ...(method === 'GET' ? {} : { 'X-C0-CSRF': csrf }),
        },
      })
      return response.data
    } catch (error) {
      if (epoch !== boundary.epoch) throw new StaleResponse()
      if (!axios.isAxiosError(error)) throw error
      const status = error.response?.status || 0
      const code =
        typeof error.response?.data?.detail === 'string'
          ? error.response.data.detail
          : ''
      if (status === 401 || status === 403) boundary.invalidate()
      throw new ApiError(status, code)
    }
  })
}

export function errorKey(error: unknown) {
  if (error instanceof ApiError) {
    if (error.code === 'key_permissions') return 'account.keyPermissions'
    if (error.status === 410) return 'errors.superseded'
    if (error.status === 409) return 'errors.conflict'
    if (error.status === 401 || error.status === 403) return 'errors.access'
    if (error.status === 404) return 'errors.missing'
    if (error.status === 422) return 'errors.invalid'
  }
  return 'errors.unavailable'
}

export async function endSession() {
  const csrf = context().csrf
  boundary.invalidate()
  const epoch = boundary.epoch
  if (!csrf) throw new ApiError(401)
  // Logout's redirect is public; it must survive erasing all protected requests.
  const response = await http.post<{ logout_url: string }>(
    localURL('auth/logout'),
    null,
    { headers: { 'X-C0-CSRF': csrf } },
  )
  if (epoch !== boundary.epoch) throw new StaleResponse()
  return response.data
}
