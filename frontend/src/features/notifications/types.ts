/**
 * Notification feature — types mirroring the backend notification contract.
 *
 * PreferencesResponse: GET /notifications/preferences
 * PreferencesUpdate:   POST /notifications/preferences (partial — only allowed keys)
 * TestResponse:        POST /notifications/test
 *
 * extra:"forbid" is enforced server-side on PreferencesUpdate, so this type
 * lists ONLY the keys the backend accepts. whatsapp_number is reserved for a
 * future phase and is never sent in updates.
 */

export interface PreferencesResponse {
  telegram_chat_id: string | null;
  email_verified: boolean;
  whatsapp_number: string | null;
  /** "HH:MM" IST or null */
  quiet_hours_start: string | null;
  /** "HH:MM" IST or null */
  quiet_hours_end: string | null;
  /** keys: "telegram", "email" */
  channels_enabled: Record<string, boolean>;
}

/**
 * Allowed keys only — backend has extra:"forbid".
 * Never include whatsapp_number (phase 2), email_verified (read-only), or
 * any key not listed here.
 */
export interface PreferencesUpdate {
  telegram_chat_id?: string | null;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
  channels_enabled?: Record<string, boolean>;
}

export interface TestNotificationRequest {
  channel: 'telegram' | 'email';
}

export interface TestNotificationResponse {
  enqueued: boolean;
  channel: string;
  detail: string;
}
