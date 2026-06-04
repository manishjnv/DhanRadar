const BASE = process.env.NEXT_PUBLIC_API_URL!;
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
    credentials: 'include',
  });
  if (!res.ok) {
    const problem = await res.json().catch(() => ({ title: res.statusText, status: res.status }));
    throw Object.assign(new Error(problem.title), { problem, status: res.status });
  }
  return res.status === 204 ? (undefined as T) : res.json();
}
