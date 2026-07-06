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
    title: 'Read your mutual fund holdings',
    description:
      'We look at the funds in your uploaded statement (CAS) to build your easy-to-read portfolio report.',
  },
  ai_insights: {
    title: 'Write AI notes about your portfolio',
    description:
      'We use AI to turn your fund data into simple, plain-language notes explaining what is going on.',
  },
  marketing: {
    title: 'Send you tips and product updates',
    description:
      'We may email you helpful articles, new features, and other updates about DhanRadar.',
  },
  portfolio_sync: {
    title: 'Save a copy of your portfolio',
    description:
      'We keep a saved copy of your fund data so your report stays up to date without re-uploading your statement every time.',
  },
  behavioral_nudges: {
    title: 'Send you portfolio reminders',
    description:
      'We may remind you to check your portfolio — for example, if a fund’s status changes.',
  },
  cross_border_ai: {
    title: 'Let AI run on servers outside India',
    description:
      'The AI service that writes your notes is hosted outside India. Your data is sent there only for that purpose.',
  },
  cross_border_notify: {
    title: 'Let alerts be sent from outside India',
    description:
      'Some of the tools we use to send you emails or messages are hosted outside India.',
  },
};
