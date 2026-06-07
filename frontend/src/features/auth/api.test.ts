/**
 * Auth API test — exercises the raw apiClient against the MSW node server.
 * We test api.get('/auth/me') which is the underpinning of useMe().
 * The MSW handler returns { user: MOCK_USER } when mockLoggedIn is true (the
 * default state of the server after resetHandlers, which is set in setup.ts).
 */
import { api } from '@/lib/apiClient';
import type { MeEnvelope } from './types';

describe('auth api — GET /auth/me', () => {
  it('returns an envelope with a user object', async () => {
    const result = await api.get<MeEnvelope>('/auth/me');
    expect(result).toHaveProperty('user');
    expect(result.user).toHaveProperty('id');
    expect(result.user).toHaveProperty('email');
    expect(result.user).toHaveProperty('tier');
  });

  it('user email matches demo account', async () => {
    const result = await api.get<MeEnvelope>('/auth/me');
    expect(result.user.email).toBe('demo@dhanradar.in');
  });

  it('user tier is a recognised value', async () => {
    const result = await api.get<MeEnvelope>('/auth/me');
    const validTiers = ['anonymous', 'free', 'pro', 'pro_plus', 'founder_lifetime'];
    expect(validTiers).toContain(result.user.tier);
  });
});
