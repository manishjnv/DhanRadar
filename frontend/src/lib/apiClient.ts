/**
 * apiClient — DhanRadar typed fetch wrapper
 *
 * Rules enforced here (architecture non-negotiables):
 *  - ALWAYS credentials: 'include'  (HttpOnly cookie auth, RS256 JWT)
 *  - NEVER an Authorization header  (non-negotiable #4)
 *  - Base path: /api/v1
 *  - Errors parsed as RFC7807 problem+json → thrown as ApiProblem
 *  - 401 → ONE silent refresh attempt via POST /auth/refresh, then retry
 */

const API_BASE =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) ?? '/api/v1';

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------
export interface ApiProblem {
  type:       string;
  title:      string;
  status:     number;
  detail?:    string;
  request_id: string;
}

export class ApiError extends Error {
  constructor(public readonly problem: ApiProblem) {
    super(`${problem.status} ${problem.title}`);
    this.name = 'ApiError';
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------
function baseHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    // NOTE: Authorization header intentionally absent — cookie auth only.
  };
}

async function parseProblem(res: Response): Promise<ApiProblem> {
  const ct = res.headers.get('content-type') ?? '';
  if (ct.includes('application/problem+json') || ct.includes('application/json')) {
    try {
      const body = await res.json();
      return {
        type:       body.type       ?? 'about:blank',
        title:      body.title      ?? res.statusText,
        status:     body.status     ?? res.status,
        detail:     body.detail,
        request_id: body.request_id ?? '',
      };
    } catch {
      // fall through to generic
    }
  }
  return {
    type:       'about:blank',
    title:      res.statusText || 'Unknown error',
    status:     res.status,
    request_id: '',
  };
}

/** Attempt one silent token refresh. Returns true if refresh succeeded. */
async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method:      'POST',
      credentials: 'include',
      headers:     baseHeaders(),
    });
    return res.ok;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Core request
// ---------------------------------------------------------------------------
async function request<T>(
  method:  string,
  path:    string,
  body?:   unknown,
  isRetry = false,
): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;

  const res = await fetch(url, {
    method,
    credentials: 'include',
    headers:     baseHeaders(),
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  if (res.status === 401 && !isRetry) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return request<T>(method, path, body, true);
    }
    // Refresh failed — parse and throw the original 401 problem
    const problem = await parseProblem(res);
    throw new ApiError(problem);
  }

  if (!res.ok) {
    const problem = await parseProblem(res);
    throw new ApiError(problem);
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T;

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------
export const api = {
  get:  <T>(path: string)                     => request<T>('GET',    path),
  post: <T>(path: string, body?: unknown)     => request<T>('POST',   path, body),
  put:  <T>(path: string, body?: unknown)     => request<T>('PUT',    path, body),
  patch:<T>(path: string, body?: unknown)     => request<T>('PATCH',  path, body),
  del:  <T>(path: string)                     => request<T>('DELETE', path),
};
