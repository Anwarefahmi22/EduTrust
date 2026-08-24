export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export type ApiEnvelope<T> = { data: T; request_id?: string }
export type ApiError = { error: { code: string; message: string; request_id?: string; details?: Record<string, unknown> } }

export async function apiRequest<T>(path: string, options: RequestInit & { token?: string; idempotencyKey?: string } = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (options.token) headers.set('Authorization', `Bearer ${options.token}`)
  if (options.idempotencyKey) headers.set('Idempotency-Key', options.idempotencyKey)
  const res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, cache: 'no-store' })
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
