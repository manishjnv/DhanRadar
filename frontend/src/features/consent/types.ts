/**
 * Consent feature — types mirroring the backend DPDP consent contract.
 *
 * ConsentState: GET /consent, POST /consent/grant, POST /consent/revoke
 *
 * All seven purposes must be present in the Record; absent keys are treated
 * as false by the backend.
 */

export type ConsentPurpose =
  | 'mf_analytics'
  | 'ai_insights'
  | 'marketing'
  | 'portfolio_sync'
  | 'behavioral_nudges'
  | 'cross_border_ai'
  | 'cross_border_notify';

export interface ConsentState {
  consents: Record<ConsentPurpose, boolean>;
  consent_version: string;
}
