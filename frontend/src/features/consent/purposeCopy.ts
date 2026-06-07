/**
 * Consent feature — human-readable copy for each DPDP consent purpose.
 *
 * All copy is plain, educational, and advisory-verb-free.
 * No buy/sell/hold/avoid/caution language anywhere in these strings.
 */
import type { ConsentPurpose } from './types';

export interface PurposeCopy {
  title: string;
  description: string;
}

export const purposeCopy: Record<ConsentPurpose, PurposeCopy> = {
  mf_analytics: {
    title: 'Analyse your mutual fund holdings',
    description:
      'We process the holdings in your CAS to produce your educational, label-based portfolio report.',
  },
  ai_insights: {
    title: 'Generate AI-assisted portfolio commentary',
    description:
      'We pass aggregated, anonymised portfolio data to our AI gateway to produce plain-language educational commentary about your holdings.',
  },
  marketing: {
    title: 'Send you educational content and product updates',
    description:
      'We may send you newsletters, feature announcements, and educational material about DhanRadar.',
  },
  portfolio_sync: {
    title: 'Periodically re-read your portfolio data',
    description:
      'We store a copy of your processed holdings so your report can be refreshed without re-uploading your CAS.',
  },
  behavioral_nudges: {
    title: 'Send you timely portfolio health reminders',
    description:
      'We may send you periodic reminders about reviewing your portfolio labels — for example, when the status of a fund changes.',
  },
  cross_border_ai: {
    title: 'Use an overseas AI service',
    description:
      'Some educational commentary is generated using an AI provider located outside India. Your data is transferred solely for this purpose.',
  },
  cross_border_notify: {
    title: 'Send alerts via overseas services',
    description:
      'Delivery of your alerts may use messaging or email providers located outside India.',
  },
};
