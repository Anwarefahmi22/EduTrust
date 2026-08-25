export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export type ApiEnvelope<T> = { data: T; request_id?: string }
export type ApiError = { error: { code: string; message: string; request_id?: string; details?: Record<string, unknown> } }

// ---------------------------------------------------------------------------
// R6 (VS10) refresh-on-expiry hook — approved scope: single in-flight refresh,
// one retry, logged-out state on second failure. Opt-in per client via
// registerSessionAuth(); without registration, apiRequest behaves exactly as
// before (no console changes). No token values are logged; the refresh token is
// kept in memory only and rotated in place after each successful refresh.
// ---------------------------------------------------------------------------

export type OnAuthChanged = (accessToken: string | null, refreshToken: string | null) => void

let registered: { refreshToken: string; onAuthChanged: OnAuthChanged } | null = null
let inflight: Promise<string | null> | null = null

/** Register the current session's refresh token + callback. The callback is invoked
 * with the rotated token pair after a successful refresh, and with (null, null) to
 * signal the logged-out state when a refresh fails. */
export function registerSessionAuth(refreshToken: string, onAuthChanged: OnAuthChanged): void {
  registered = { refreshToken, onAuthChanged }
  inflight = null
}

export function clearSessionAuth(): void {
  registered = null
  inflight = null
}

function singleFlightRefresh(): Promise<string | null> {
  if (!registered) return Promise.resolve(null)
  if (!inflight) {
    const rt = registered.refreshToken
    inflight = (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: rt }),
          cache: 'no-store',
        })
        if (!res.ok) return null
        const body = (await res.json().catch(() => ({}))) as ApiEnvelope<{ access_token?: string; refresh_token?: string }>
        const access = body.data?.access_token
        const refresh = body.data?.refresh_token
        if (!access || !refresh || !registered) return null
        // Strict rotation: the just-used refresh token is now dead server-side;
        // store the new one (in memory only) for the next in-flight refresh.
        registered.refreshToken = refresh
        registered.onAuthChanged(access, refresh)
        return access
      } catch {
        return null
      }
    })()
    inflight.finally(() => {
      inflight = null
    })
  }
  return inflight
}

export async function apiRequest<T>(path: string, options: RequestInit & { token?: string; idempotencyKey?: string } = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (options.token) headers.set('Authorization', `Bearer ${options.token}`)
  if (options.idempotencyKey) headers.set('Idempotency-Key', options.idempotencyKey)
  const doFetch = (token?: string) =>
    fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: token ? new Headers({ ...headers, Authorization: `Bearer ${token}` }) : headers,
      cache: 'no-store',
    })
  let res = await doFetch(options.token)
  // R6 hook: on 401 with a registered session, attempt ONE in-flight refresh and
  // retry the original request once with the rotated access token. A failed
  // refresh (or a second 401) falls through to the error path; the registered
  // callback already received (null, null) → the client's logged-out state.
  if (res.status === 401 && registered) {
    const fresh = await singleFlightRefresh()
    if (fresh) {
      res = await doFetch(fresh)
    }
  }
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = body as ApiError
    throw new Error(err.error?.message || `API request failed: ${res.status}`)
  }
  return body as T
}

export async function apiGet<T>(path: string, token?: string): Promise<T> {
  return apiRequest<T>(path, { method: 'GET', token })
}

export async function apiPost<T>(path: string, data: unknown, token?: string, idempotencyKey?: string): Promise<T> {
  return apiRequest<T>(path, { method: 'POST', body: JSON.stringify(data), token, idempotencyKey })
}

export async function apiPatch<T>(path: string, data: unknown, token?: string): Promise<T> {
  return apiRequest<T>(path, { method: 'PATCH', body: JSON.stringify(data), token })
}
