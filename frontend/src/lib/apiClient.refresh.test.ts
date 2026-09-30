import { afterEach, describe, expect, it, vi } from 'vitest';
import { tryRefresh } from '@/lib/apiClient';

describe('tryRefresh', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('is single-flight: concurrent callers share one POST /auth/refresh', async () => {
    let release: (r: Response) => void = () => {};
    const fetchMock = vi.fn(() => new Promise<Response>((r) => (release = r)));
    vi.stubGlobal('fetch', fetchMock);

    const a = tryRefresh();
    const b = tryRefresh();
    release(new Response(null, { status: 200 }));

    expect(await a).toBe(true);
    expect(await b).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Once settled, the next call makes a fresh request.
    fetchMock.mockImplementationOnce(() => Promise.resolve(new Response(null, { status: 401 })));
    expect(await tryRefresh()).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
