/**
 * Auth feature — types mirroring the backend `auth` contract
 * (dhanradar/auth/schemas.py :: UserResponse).
 *
 * No token material is ever modelled here — auth is cookie-only (HttpOnly
 * __Host-* cookies, RS256). The JS layer only ever sees the user profile.
 */

export type UserTier =
  | 'anonymous'
  | 'free'
  | 'pro'
  | 'pro_plus'
  | 'founder_lifetime';

export interface AuthUser {
  id: string;
  email: string;
  tier: UserTier;
  totp_verified: boolean;
  /** Written only by Onboarding; null until the user completes it. */
  risk_profile: string | null;
  dpdp_consent_version: string | null;
}

/** POST /auth/login and /auth/signup envelope. */
export interface AuthEnvelope {
  message: string;
  user: AuthUser;
}

/** GET /auth/me envelope. */
export interface MeEnvelope {
  user: AuthUser;
}

export interface Credentials {
  email: string;
  password: string;
}
