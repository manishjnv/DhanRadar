/**
 * Consent API test — exercises the apiClient against the MSW node server.
 * Proves the GET /consent + POST grant/revoke round-trip and contract shape.
 * Self-contained: revokes first so it does not depend on shared mock state.
 */
import { api } from '@/lib/apiClient';
import type { ConsentState } from './types';

describe('consent api — /consent grant + revoke', () => {
  it('GET /consent returns a consents map and a version', async () => {
    const state = await api.get<ConsentState>('/consent');
    expect(state).toHaveProperty('consent_version', '2026-06-01');
    expect(state.consents).toHaveProperty('mf_analytics');
  });

  it('grant flips a purpose true, revoke flips it back false', async () => {
    // Start from a known state.
    let s = await api.post<ConsentState>('/consent/revoke', { purposes: ['mf_analytics'] });
    expect(s.consents.mf_analytics).toBe(false);

    s = await api.post<ConsentState>('/consent/grant', { purposes: ['mf_analytics'] });
    expect(s.consents.mf_analytics).toBe(true);

    s = await api.post<ConsentState>('/consent/revoke', { purposes: ['mf_analytics'] });
    expect(s.consents.mf_analytics).toBe(false);
  });

  it('grant of one purpose does not clobber a sibling', async () => {
    await api.post<ConsentState>('/consent/grant', { purposes: ['mf_analytics'] });
    const s = await api.post<ConsentState>('/consent/grant', { purposes: ['cross_border_ai'] });
    expect(s.consents.mf_analytics).toBe(true);
    expect(s.consents.cross_border_ai).toBe(true);
  });
});
