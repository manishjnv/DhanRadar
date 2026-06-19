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
  /**
   * True when user.id ∈ settings.admin_user_ids on the backend.
   * Requires backend change to /auth/me response body (Admin.md §2).
   * Undefined on older backend builds — treated as false by AdminGuard.
   */
  is_admin?: boolean;
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

/** POST /auth/totp/login */
export interface TotpCredentials {
  email: string;
  code: string;
}

/** POST /auth/totp/setup response */
export interface TotpSetupResponse {
  provisioning_uri: string;
  secret: string;
}

/** POST /auth/totp/verify request */
export interface TotpVerifyRequest {
  code: string;
}

/** POST /auth/email-otp/request body */
export interface EmailOtpRequestBody {
  email: string;
}

/** POST /auth/email-otp/request 202 response */
export interface EmailOtpRequestResponse {
  message: string;
}

/** POST /auth/email-otp/login body */
export interface EmailOtpCredentials {
  email: string;
  code: string;
}
