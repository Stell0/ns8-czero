import axios, { type AxiosRequestConfig } from 'axios'

export class ApiError extends Error {
  constructor(
    public status: number,
    public code = '',
    public reason = '',
    public field = '',
    public approvalToken = '',
  ) {
    super('C0 request failed')
  }
}

export class StaleResponse extends Error {}

// An aborted request can still settle. The epoch also guards parsed responses.
export class AccessBoundary {
  epoch = 0
  private controllers = new Set<AbortController>()
  private listeners = new Set<(rejection?: ApiError) => void>()
  invalidate(rejection?: ApiError) {
    this.epoch++
    for (const controller of this.controllers) controller.abort()
    this.controllers.clear()
    for (const listener of this.listeners) listener(rejection)
  }
  onClear(listener: (rejection?: ApiError) => void) {
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
  reviewedCsrf?: string,
): Promise<T> {
  const epoch = boundary.epoch
  return boundary.run(async (signal) => {
    const method = (options.method || 'GET').toUpperCase()
    const csrf = reviewedCsrf ?? context().csrf
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
      const data = error.response?.data
      const failure = new ApiError(
        status,
        code,
        typeof data?.reason === 'string' ? data.reason : '',
        typeof data?.field === 'string' ? data.field : '',
        status === 422 &&
          code === 'pdf_extraction_approval_required' &&
          typeof data?.approval_token === 'string' &&
          data.approval_token.length <= 80
          ? data.approval_token
          : '',
      )
      if (status === 401 || status === 403) boundary.invalidate(failure)
      throw failure
    }
  })
}

export function errorKey(error: unknown) {
  if (error instanceof ApiError) {
    if (error.code === 'invalid_automatic_source') {
      const reason = automaticSourceReasons.includes(error.reason)
        ? error.reason
        : 'invalid_automatic_source'
      return `automatic.errors.${reason}`
    }
    if (
      ['connection_request_unavailable', 'invalid_consent'].includes(error.code)
    )
      return 'consent.unavailable'
    if (error.code === 'key_permissions') return 'account.keyPermissions'
    if (error.status === 410) return 'errors.superseded'
    if (error.status === 409) return 'errors.conflict'
    if (error.status === 401 || error.status === 403) return 'errors.access'
    if (error.status === 404) return 'errors.missing'
    if (error.code === 'pdf_unlock_unavailable')
      return 'sources.pdf.pdf_unlock_unavailable'
    if (error.status === 422 && error.code === 'invalid_pdf')
      return 'sources.pdf.invalid_pdf'
    if (error.status === 422) return 'errors.invalid'
  }
  return 'errors.unavailable'
}

const automaticSourceReasons = [
  'invalid_automatic_source',
  'invalid_github_repositories',
  'invalid_github_selection',
  'invalid_github_ref',
  'invalid_drive_folder',
  'drive_unavailable',
  'drive_reconnect_required',
  'drive_offline_required',
  'drive_preview_required',
  'drive_item_unavailable',
  'drive_provider_error',
  'drive_scope_mismatch',
  'invalid_source_configuration',
  'invalid_source_selection',
  'invalid_source_limit',
  'invalid_source_name',
  'invalid_source_kind',
  'invalid_source_interval',
  'invalid_source_enabled',
  'invalid_revision',
  'invalid_source_replay_key',
  'invalid_source_action',
  'invalid_website_configuration',
  'invalid_website_selection',
  'explicit_documentation_roots_required',
  'website_destination_not_approved',
  'invalid_public_url',
  'github_repository_unavailable',
  'source_http_403',
  'source_http_429',
  'source_http_404',
  'source_transport_failed',
]

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
