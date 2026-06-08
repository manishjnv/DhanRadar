/**
 * Onboarding feature — types mirroring the backend `onboarding` contract.
 *
 * RiskProfile values are educational labels only — no advisory verbs, no
 * numeric scores. Written by the risk-quiz route; read by AuthGuard for
 * the cold-start redirect.
 */

export type RiskProfile = 'conservative' | 'moderate' | 'aggressive';

export interface RiskQuizRequest {
  /** Five option indices, each 0..3 (0 = most conservative, 3 = most aggressive). */
  answers: number[];
}

export interface RiskQuizResponse {
  risk_profile: RiskProfile;
}
