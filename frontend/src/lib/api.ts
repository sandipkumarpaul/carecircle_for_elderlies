export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

// Session-bound CSRF token stays in memory; JWT stays in an HttpOnly cookie.
let csrfToken: string | null = null;
export function setCsrfToken(token: string | null) { csrfToken = token; }

export async function refreshCsrf() {
  const result = await api<{ csrf_token: string }>('/auth/csrf');
  setCsrfToken(result.csrf_token);
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (!path.startsWith('/') || path.startsWith('//')) {
    throw new Error('Use a relative API path beginning with one slash');
  }
  const method = (options.method ?? 'GET').toUpperCase();
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    if (!csrfToken) throw new ApiError(0, 'csrf_unavailable', 'Sign in before making changes');
    headers.set('X-CSRF-Token', csrfToken);
  }
  const response = await fetch(`/api/v1${path}`, { ...options, method, headers, credentials: 'include' });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.error?.code ?? 'request_failed',
      body?.error?.message ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
