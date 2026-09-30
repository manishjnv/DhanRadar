/**
 * Data deletion + retention policy for UI copy.
 * Mirrors backend/dhanradar/compliance/data_policy.py (the source of truth) —
 * change both together. Dates shown to a user come from the API, not from here.
 */
export const ERASURE_WAIT_DAYS = 7;
export const ERASURE_DUE_DAYS = 30;
export const LEGAL_RECORD_YEARS = 8;
export const LOG_RETENTION_YEARS = 1;
export const FULL_BACKUP_DAYS = 90;
export const SUPPORT_EMAIL = 'connect@dhanradar.com';
