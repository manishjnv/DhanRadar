/**
 * Lightweight sanity checks on the MSW handlers array.
 * Ensures the handlers are non-empty and that key routes we depend on are
 * present, without re-testing the actual network behavior (that is done in
 * the feature api tests).
 */
import { handlers } from './handlers';

describe('MSW handlers', () => {
  it('is a non-empty array', () => {
    expect(Array.isArray(handlers)).toBe(true);
    expect(handlers.length).toBeGreaterThan(0);
  });

  it('contains at least 10 registered routes (launch wedge coverage)', () => {
    expect(handlers.length).toBeGreaterThanOrEqual(10);
  });

  it('each handler has an info property with a method and path', () => {
    for (const handler of handlers) {
      // MSW v2 handlers expose `info` with `method` and `path`
      expect(handler).toHaveProperty('info');
      expect((handler as { info: { method: string; path: string } }).info).toHaveProperty('method');
      expect((handler as { info: { method: string; path: string } }).info).toHaveProperty('path');
    }
  });

  it('has a handler for GET /api/v1/auth/me', () => {
    const found = handlers.some((h) => {
      const info = (h as { info: { method: string; path: string } }).info;
      return info.method === 'GET' && String(info.path).includes('/auth/me');
    });
    expect(found).toBe(true);
  });

  it('has a handler for POST /api/v1/mf/upload/cas', () => {
    const found = handlers.some((h) => {
      const info = (h as { info: { method: string; path: string } }).info;
      return info.method === 'POST' && String(info.path).includes('/mf/upload/cas');
    });
    expect(found).toBe(true);
  });

  it('has a handler for GET /api/v1/market/mood', () => {
    const found = handlers.some((h) => {
      const info = (h as { info: { method: string; path: string } }).info;
      return info.method === 'GET' && String(info.path).includes('/market/mood');
    });
    expect(found).toBe(true);
  });
});
