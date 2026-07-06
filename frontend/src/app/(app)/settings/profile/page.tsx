'use client';

/**
 * Customer Profile — consolidated account, security, privacy, and preferences hub.
 *
 * 14 tabs: Overview, Personal, Investment, Risk, Privacy & Consent (REAL),
 * Accounts, Documents, Security, Notifications, Preferences, Connected,
 * Activity, Data & Privacy, Support.
 *
 * Only Privacy & Consent is wired to real backend APIs (moved from the
 * standalone privacy page). All other tabs are static/illustrative placeholders
 * with "Illustrative — coming soon" badges.
 */

import * as React from 'react';
import { toast } from 'sonner';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardBody,
} from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { cn } from '@/lib/cn';
import { useMe } from '@/features/auth/api';
import { useConsent, useGrantConsent, useRevokeConsent } from '@/features/consent/api';
import { purposeCopy } from '@/features/consent/purposeCopy';
import type { ConsentPurpose } from '@/features/consent/types';

// Display order — data-processing purposes first, cross-border transfers last.
const PURPOSE_ORDER: ConsentPurpose[] = [
  'mf_analytics',
  'ai_insights',
  'portfolio_sync',
  'behavioral_nudges',
  'marketing',
  'cross_border_ai',
  'cross_border_notify',
];

// Plain-English grouping for the consent tab — purely presentational. Each
// purpose is still its own real, individually-toggled backend consent; this
// only changes how the 7 toggles are organised on screen so a customer can
// scan them faster. Order within a group follows PURPOSE_ORDER.
const CONSENT_GROUPS: { heading: string; blurb: string; purposes: ConsentPurpose[] }[] = [
  {
    heading: 'Your investments',
    blurb: 'Reading and remembering your fund data so we can build your report.',
    purposes: ['mf_analytics', 'portfolio_sync'],
  },
  {
    heading: 'AI-written notes',
    blurb: 'Using AI (partly hosted outside India) to explain your portfolio in plain language.',
    purposes: ['ai_insights', 'cross_border_ai'],
  },
  {
    heading: 'Reminders & updates',
    blurb: 'Messages we send you — some delivered using tools hosted outside India.',
    purposes: ['behavioral_nudges', 'marketing', 'cross_border_notify'],
  },
];

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------
type TabId =
  | 'overview'
  | 'personal'
  | 'investment'
  | 'risk'
  | 'privacy'
  | 'accounts'
  | 'documents'
  | 'security'
  | 'notifications'
  | 'preferences'
  | 'connected'
  | 'activity'
  | 'data'
  | 'support';

interface Tab {
  id: TabId;
  label: string;
}

const TABS: Tab[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'personal', label: 'Personal' },
  { id: 'investment', label: 'Investment' },
  { id: 'risk', label: 'Risk' },
  { id: 'privacy', label: 'Privacy & Consent' },
  { id: 'accounts', label: 'Accounts' },
  { id: 'documents', label: 'Documents' },
  { id: 'security', label: 'Security' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'preferences', label: 'Preferences' },
  { id: 'connected', label: 'Connected' },
  { id: 'activity', label: 'Activity' },
  { id: 'data', label: 'Data & Privacy' },
  { id: 'support', label: 'Support' },
];

// ---------------------------------------------------------------------------
// Toggle — accessible role="switch" styled with tokens.
// ---------------------------------------------------------------------------
interface ToggleProps {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label: string;
}

function Toggle({ id, checked, onChange, disabled = false, label }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={cn(
        'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent',
        'transition-colors duration-200',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
        'disabled:pointer-events-none disabled:opacity-40',
        checked ? 'bg-royal' : 'bg-surface-3',
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm',
          'transform transition-transform duration-200',
          checked ? 'translate-x-5' : 'translate-x-0',
        )}
      />
    </button>
  );
}

// ---------------------------------------------------------------------------
// IllustrativeBadge — small unobtrusive tag for dummy sections.
// ---------------------------------------------------------------------------
function IllustrativeBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-violet/10 px-2 py-0.5 text-caption font-medium text-violet">
      <span className="text-[10px]">◆</span>
      Illustrative — coming soon
    </span>
  );
}

// ---------------------------------------------------------------------------
// FieldRow — label + value row (mirroring the mockup pattern).
// ---------------------------------------------------------------------------
interface FieldRowProps {
  label: string;
  value: React.ReactNode;
  badge?: React.ReactNode;
  action?: React.ReactNode;
}

function FieldRow({ label, value, badge, action }: FieldRowProps) {
  return (
    <div className="flex items-center gap-3 border-b border-line py-3 last:border-b-0">
      <div className="w-32 shrink-0 text-caption text-ink-muted">{label}</div>
      <div className="flex min-w-0 flex-1 items-center gap-2 text-body font-medium text-ink">
        {value}
        {badge && <span className="shrink-0">{badge}</span>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProfileHero — top banner with real data from useMe().
// ---------------------------------------------------------------------------
function ProfileHero({ email, tier }: { email: string; tier: string }) {
  // Compute initials from email (first 2 letters before @).
  const initials = email
    .split('@')[0]
    .slice(0, 2)
    .toUpperCase();

  // Tier badge formatting.
  const tierLabel =
    tier === 'free'
      ? 'Free'
      : tier === 'pro'
        ? 'Pro'
        : tier === 'pro_plus'
          ? 'Pro+'
          : tier === 'founder_lifetime'
            ? 'Founder'
            : tier;

  return (
    <Card className="mb-4 overflow-hidden bg-gradient-to-br from-navy via-navy to-royal text-white">
      <CardBody className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center">
        {/* Avatar */}
        <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-royal to-emerald text-h3 font-bold">
          {initials}
        </div>

        {/* Identity */}
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-h4 font-bold">{email}</span>
            <span className="rounded-full bg-white/20 px-3 py-1 text-caption font-bold uppercase tracking-wide text-white">
              {tierLabel}
            </span>
          </div>
          <p className="mt-1 text-small text-white/70">
            Member since {new Date().toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })}
          </p>
        </div>

        {/* Completion ring placeholder — static 82% for now */}
        <div className="flex flex-col items-center gap-1">
          <div className="relative flex h-20 w-20 items-center justify-center">
            {/* SVG ring would go here; simplified to text for now */}
            <div className="text-h3 font-bold">82%</div>
          </div>
          <p className="text-caption uppercase tracking-wide text-white/70">
            Profile Complete
          </p>
        </div>
      </CardBody>

      {/* Stats row — all illustrative placeholder stats except the tier */}
      <div className="grid grid-cols-2 gap-px bg-white/10 sm:grid-cols-3 md:grid-cols-6">
        {[
          ['Portfolio Value', '₹48.3L'],
          ['Linked Accounts', '5'],
          ['KYC Status', 'Verified'],
          ['Consents', '7 purposes'],
          ['Last Sync', '2h ago'],
          ['Last Login', 'Today'],
        ].map(([label, value], idx) => (
          <div key={idx} className="bg-white/5 px-3 py-2.5">
            <div className="text-[9px] uppercase tracking-wide text-white/60">
              {label}
            </div>
            <div className="mt-1 text-body font-bold">{value}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Tab panels (13 dummy + 1 real Privacy & Consent).
// ---------------------------------------------------------------------------

function OverviewPanel() {
  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Profile at a glance</CardTitle>
            <CardDescription>Your DhanRadar account summary</CardDescription>
          </CardHeader>
          <CardBody>
            <FieldRow label="Full Name" value="Sample User" />
            <FieldRow label="Customer ID" value={<code className="font-mono">DR-48213905</code>} />
            <FieldRow label="Member Since" value={<code className="font-mono">14 Mar 2025</code>} />
            <FieldRow
              label="KYC Status"
              value="Verified via CKYC"
              badge={<span className="rounded bg-emerald/10 px-2 py-0.5 text-caption font-bold text-emerald">Verified</span>}
            />
            <FieldRow label="Risk Profile" value="Moderate-Aggressive" />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Completion checklist</CardTitle>
            <CardDescription>Finish these to reach 100%</CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            {[
              ['Personal details verified', true],
              ['KYC completed', true],
              ['Risk assessment done', true],
              ['Bank account linked', true],
              ['Nominee added', false],
              ['Investment profile complete', false],
            ].map(([text, done], idx) => (
              <div key={idx} className="flex items-center gap-3 border-b border-line pb-3 last:border-b-0 last:pb-0">
                <span
                  className={cn(
                    'flex h-5 w-5 shrink-0 items-center justify-center rounded text-caption font-bold',
                    done ? 'bg-emerald/10 text-emerald' : 'bg-amber/10 text-amber',
                  )}
                >
                  {done ? '✓' : '!'}
                </span>
                <span className={cn('flex-1 text-small', done ? 'text-ink-muted' : 'text-ink font-medium')}>
                  {text}
                </span>
                {done ? (
                  <span className="text-caption text-ink-muted">Done</span>
                ) : (
                  <Button variant="outline" size="sm">
                    Complete
                  </Button>
                )}
              </div>
            ))}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardBody className="flex items-start gap-3 bg-royal/10 p-4">
          <span className="text-h5 font-bold text-royal">→</span>
          <p className="text-small text-ink-secondary">
            <strong className="font-semibold text-ink">Your profile is 82% complete.</strong>{' '}
            Adding your nominee and completing your investment profile unlocks more accurate
            recommendations, goal planning and a smoother withdrawal process later. These two steps
            take about 3 minutes.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}

function PersonalPanel() {
  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Identity</CardTitle>
            <CardDescription>Verified against official records</CardDescription>
          </CardHeader>
          <CardBody>
            <FieldRow label="Full Name" value="Aarav Sharma" />
            <FieldRow label="Date of Birth" value={<code className="font-mono">12 Aug 1990</code>} />
            <FieldRow
              label="PAN"
              value={<code className="font-mono">ABCDE••••F</code>}
              badge={<span className="rounded bg-emerald/10 px-2 py-0.5 text-caption font-bold text-emerald">Verified</span>}
              action={<Button variant="outline" size="sm">Update</Button>}
            />
            <FieldRow
              label="Aadhaar"
              value={<code className="font-mono">XXXX XXXX 4821</code>}
              badge={<span className="rounded bg-emerald/10 px-2 py-0.5 text-caption font-bold text-emerald">Linked</span>}
            />
            <FieldRow label="Tax Residency" value="India (Resident)" />
            <FieldRow label="Marital Status" value="Married" />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Contact &amp; address</CardTitle>
            <CardDescription>Used for statements and alerts</CardDescription>
          </CardHeader>
          <CardBody>
            <FieldRow
              label="Email"
              value="aarav.s@example.com"
              badge={<span className="rounded bg-emerald/10 px-2 py-0.5 text-caption font-bold text-emerald">Verified</span>}
              action={<Button variant="outline" size="sm">Change</Button>}
            />
            <FieldRow
              label="Mobile"
              value={<code className="font-mono">+91 98765 ••210</code>}
              badge={<span className="rounded bg-emerald/10 px-2 py-0.5 text-caption font-bold text-emerald">Verified</span>}
              action={<Button variant="outline" size="sm">Change</Button>}
            />
            <FieldRow label="Address" value="Sector 26, Gurugram, HR 122002" action={<Button variant="outline" size="sm">Update</Button>} />
            <FieldRow label="Occupation" value="Salaried — IT/Software" />
            <FieldRow
              label="Nominee"
              value="Not added"
              badge={<span className="rounded bg-amber/10 px-2 py-0.5 text-caption font-bold text-amber">Pending</span>}
              action={<Button variant="outline" size="sm">Add</Button>}
            />
          </CardBody>
        </Card>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="primary">Update Personal Details</Button>
        <Button variant="outline">Change Mobile</Button>
        <Button variant="outline">Change Email</Button>
        <Button variant="outline">Add Nominee</Button>
      </div>
    </div>
  );
}

function InvestmentPanel() {
  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <Card>
        <CardHeader>
          <CardTitle>Investment profile</CardTitle>
          <CardDescription>
            Powers your recommendations, goal planning, calculators and fund-fit scores
          </CardDescription>
        </CardHeader>
        <CardBody className="grid gap-x-6 gap-y-3 md:grid-cols-3">
          <div className="flex flex-col gap-3">
            <FieldRow label="Risk Appetite" value="Moderate-Aggressive" />
            <FieldRow label="Investment Horizon" value="Long-term (10+ yrs)" />
            <FieldRow label="Experience" value="Intermediate (5 yrs)" />
            <FieldRow label="Monthly Capacity" value={<code className="font-mono">₹42,000</code>} />
          </div>
          <div className="flex flex-col gap-3">
            <FieldRow label="Annual Income" value={<code className="font-mono">₹24–36 L</code>} />
            <FieldRow label="Net Worth" value={<code className="font-mono">₹85 L</code>} />
            <FieldRow label="Tax Preference" value="Old regime · 80C" />
            <FieldRow label="Growth vs Income" value="Growth-focused" />
          </div>
          <div className="flex flex-col gap-3">
            <FieldRow
              label="Auto-invest"
              value="Enabled"
              badge={<span className="rounded bg-emerald/10 px-2 py-0.5 text-caption font-bold text-emerald">On</span>}
            />
            <FieldRow label="ESG Preference" value="Preferred" />
            <FieldRow label="Objective" value="Wealth creation" />
            <FieldRow label="Direct/Regular" value="Direct plans only" />
          </div>
        </CardBody>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Preferred categories</CardTitle>
            <CardDescription>Used to personalise discovery</CardDescription>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {['Flexi Cap', 'Small Cap', 'Mid Cap', 'ELSS', 'Index', 'Large Cap', 'Hybrid', 'International'].map(
                (cat, idx) => (
                  <span
                    key={cat}
                    className={cn(
                      'rounded-md border px-3 py-1.5 text-small font-medium',
                      idx < 5
                        ? 'border-royal bg-royal text-white'
                        : 'border-line bg-surface-2 text-ink-secondary',
                    )}
                  >
                    {cat}
                  </span>
                ),
              )}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Preferred asset classes</CardTitle>
            <CardDescription>Across the DhanRadar ecosystem</CardDescription>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {['Equity MF', 'Debt MF', 'ETFs', 'Gold', 'Index Funds', 'REITs', 'International'].map(
                (asset, idx) => (
                  <span
                    key={asset}
                    className={cn(
                      'rounded-md border px-3 py-1.5 text-small font-medium',
                      idx < 4
                        ? 'border-royal bg-royal text-white'
                        : 'border-line bg-surface-2 text-ink-secondary',
                    )}
                  >
                    {asset}
                  </span>
                ),
              )}
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardBody className="flex items-start gap-3 bg-royal/10 p-4">
          <span className="text-h5 font-bold text-royal">→</span>
          <p className="text-small text-ink-secondary">
            <strong className="font-semibold text-ink">
              This profile is read by Portfolio, Recommendations, Goal Planner, Calculators and Fund Detail.
            </strong>{' '}
            Keeping it current means every fund-fit score, suggested SIP and risk warning across DhanRadar
            is tailored to your real situation — update it whenever your income, goals or risk comfort changes.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}

function RiskPanel() {
  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <Card>
        <CardHeader>
          <CardTitle>Risk assessment</CardTitle>
          <CardDescription>
            Last completed 12 Mar 2026 · Version 2.1 · Valid till 12 Mar 2027
          </CardDescription>
        </CardHeader>
        <CardBody className="flex flex-col gap-4">
          <div className="grid gap-4 md:grid-cols-[280px,1fr]">
            {/* Gauge placeholder */}
            <div className="flex flex-col items-center gap-2">
              <div className="flex h-32 w-32 items-center justify-center rounded-full border-8 border-amber/20 bg-amber/10">
                <div className="text-center">
                  <div className="text-h2 font-bold text-amber">68</div>
                  <div className="text-caption uppercase tracking-wide text-ink-muted">
                    Risk Score
                  </div>
                </div>
              </div>
              <div className="text-center">
                <div className="text-h5 font-bold text-amber">Moderate-Aggressive</div>
                <div className="text-caption text-ink-muted">
                  Comfortable with swings for growth
                </div>
              </div>
            </div>

            {/* Meta grid */}
            <div className="grid grid-cols-2 gap-3">
              {[
                ['Risk Category', 'Moderate-Aggressive', 'text-amber'],
                ['Score', '68 / 100', 'text-ink'],
                ['Assessed On', '12 Mar 2026', 'text-ink'],
                ['Valid Until', '12 Mar 2027', 'text-amber'],
              ].map(([label, value, colorClass], idx) => (
                <div key={idx} className="rounded-lg border border-line p-3">
                  <div className="text-caption font-bold uppercase tracking-wide text-ink-muted">
                    {label}
                  </div>
                  <div className={cn('mt-1 text-body font-bold', colorClass)}>{value}</div>
                </div>
              ))}
            </div>
          </div>

          <Card>
            <CardBody className="flex items-start gap-3 bg-amber/10 p-4">
              <span className="text-h5 font-bold text-amber">⚠</span>
              <p className="text-small text-ink-secondary">
                <strong className="font-semibold text-ink">
                  Your assessment expires in 18 days (12 Mar 2027).
                </strong>{' '}
                SEBI guidance recommends reassessing risk annually. An up-to-date profile keeps your
                recommendations and fund-fit scores accurate. It takes about 4 minutes.
              </p>
            </CardBody>
          </Card>

          <div className="flex flex-wrap gap-2">
            <Button variant="primary">Reassess Now</Button>
            <Button variant="outline">View Questionnaire</Button>
            <Button variant="outline">Download Report</Button>
            <Button variant="outline">View History</Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

// Privacy & Consent — REAL, moved from privacy/page.tsx
function PrivacyPanel() {
  const { data: consent, isLoading, isError, refetch } = useConsent();
  const grant = useGrantConsent();
  const revoke = useRevokeConsent();

  const pending = grant.isPending || revoke.isPending;

  function handleToggle(purpose: ConsentPurpose, next: boolean) {
    const mutation = next ? grant : revoke;
    mutation.mutate(
      { purposes: [purpose] },
      {
        onSuccess: () =>
          toast.success(next ? 'Consent granted' : 'Consent withdrawn'),
        onError: () => toast.error('Could not update your consent. Please try again.'),
      },
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-64 rounded-md" />
        <Card>
          <CardBody className="flex flex-col gap-5">
            <Skeleton className="h-14 w-full rounded-md" />
            <Skeleton className="h-14 w-full rounded-md" />
            <Skeleton className="h-14 w-full rounded-md" />
          </CardBody>
        </Card>
      </div>
    );
  }

  if (isError || !consent) {
    return (
      <ErrorCard
        title="Could not load your consent settings"
        message="Check your connection and try again."
        onRetry={() => refetch()}
      />
    );
  }

  const activeCount = Object.values(consent.consents).filter(Boolean).length;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>What can DhanRadar do with your data?</CardTitle>
          <CardDescription>
            Turn each one on or off. You can change your mind anytime — some features just won&rsquo;t
            work until the related permission is on.
          </CardDescription>
        </CardHeader>
        <CardBody className="flex flex-col gap-7">
          {CONSENT_GROUPS.map((group, groupIdx) => (
            <div key={group.heading} className="flex flex-col gap-4">
              {groupIdx > 0 && <div className="border-t border-line" />}
              <div className="flex flex-col gap-0.5">
                <h4 className="text-body font-semibold text-ink">{group.heading}</h4>
                <p className="text-caption text-ink-muted">{group.blurb}</p>
              </div>
              <div className="flex flex-col gap-4">
                {group.purposes.map((purpose) => {
                  const copy = purposeCopy[purpose];
                  const granted = consent.consents[purpose] ?? false;
                  return (
                    <div
                      key={purpose}
                      className="flex items-start justify-between gap-4 rounded-md bg-surface-2 p-3"
                    >
                      <div className="flex flex-col gap-0.5">
                        <label
                          htmlFor={`consent-${purpose}`}
                          className="cursor-pointer text-body font-medium text-ink"
                        >
                          {copy.title}
                        </label>
                        <p className="text-caption text-ink-muted">{copy.description}</p>
                      </div>
                      <Toggle
                        id={`consent-${purpose}`}
                        checked={granted}
                        disabled={pending}
                        onChange={(next) => handleToggle(purpose, next)}
                        label={`${granted ? 'Turn off' : 'Turn on'}: ${copy.title}`}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </CardBody>
      </Card>

      <Card>
        <CardBody className="flex items-start gap-3 bg-royal/10 p-4">
          <span className="text-h5 font-bold text-royal">→</span>
          <p className="text-small text-ink-secondary">
            <strong className="font-semibold text-ink">
              {activeCount} of {PURPOSE_ORDER.length} permissions are on.
            </strong>{' '}
            This is the one place to manage all of them. Turning a permission off never deletes or
            un-does anything we already did — it only stops future use.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}

function AccountsPanel() {
  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Bank accounts &amp; payments</CardTitle>
            <CardDescription>For SIP auto-debit and redemptions</CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            {[
              {
                logo: 'H',
                color: '#004C8F',
                name: 'HDFC Bank ••4821',
                badge: 'Primary',
                meta: 'Savings · Auto-debit active',
                status: 'Verified',
              },
              {
                logo: 'U',
                color: '#5F259F',
                name: 'UPI AutoPay',
                meta: 'aarav@okhdfcbank · 2 active mandates',
                action: true,
              },
            ].map((acc, idx) => (
              <div key={idx} className="flex items-center gap-3 border-b border-line pb-3 last:border-b-0 last:pb-0">
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-body font-bold text-white"
                  style={{ backgroundColor: acc.color }}
                >
                  {acc.logo}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-body font-bold text-ink">
                    {acc.name}
                    {acc.badge && (
                      <span className="rounded bg-emerald/10 px-2 py-0.5 text-caption font-bold text-emerald">
                        {acc.badge}
                      </span>
                    )}
                  </div>
                  <div className="text-caption text-ink-muted">{acc.meta}</div>
                </div>
                {acc.status ? (
                  <span className="flex items-center gap-1.5 text-caption font-medium text-emerald">
                    <span className="h-2 w-2 rounded-full bg-emerald" />
                    {acc.status}
                  </span>
                ) : (
                  <Button variant="outline" size="sm">
                    Manage
                  </Button>
                )}
              </div>
            ))}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Broker &amp; RTA accounts</CardTitle>
            <CardDescription>Sources for portfolio sync</CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            {[
              { logo: 'B', color: '#00518F', name: 'BSE Star MF', meta: 'Synced 2h ago', connected: true },
              { logo: 'M', color: '#1A7F5A', name: 'MF Central', meta: 'Synced 1d ago', connected: true },
              { logo: 'C', color: '#E2761B', name: 'CAMS', meta: 'Synced 2h ago', connected: true },
              { logo: 'K', color: '#7B2D8E', name: 'KFintech', meta: 'Not connected', connected: false },
            ].map((acc, idx) => (
              <div key={idx} className="flex items-center gap-3 border-b border-line pb-3 last:border-b-0 last:pb-0">
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-body font-bold text-white"
                  style={{ backgroundColor: acc.color }}
                >
                  {acc.logo}
                </div>
                <div className="flex-1">
                  <div className="text-body font-bold text-ink">{acc.name}</div>
                  <div className="text-caption text-ink-muted">{acc.meta}</div>
                </div>
                {acc.connected ? (
                  <span className="flex items-center gap-1.5 text-caption font-medium text-emerald">
                    <span className="h-2 w-2 rounded-full bg-emerald" />
                    Connected
                  </span>
                ) : (
                  <Button variant="outline" size="sm">
                    Connect
                  </Button>
                )}
              </div>
            ))}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function DocumentsPanel() {
  const docs = [
    { icon: '📄', name: 'PAN Card', meta: 'Verified · PDF', color: 'text-red' },
    { icon: '🆔', name: 'Aadhaar', meta: 'Masked · PDF', color: 'text-royal' },
    { icon: '🗂', name: 'CKYC Record', meta: 'Verified', color: 'text-violet' },
    { icon: '📝', name: 'Consent PDFs', meta: '7 documents', color: 'text-emerald' },
    { icon: '🎯', name: 'Risk Report', meta: 'v2.1 · Mar 2026', color: 'text-amber' },
    { icon: '📊', name: 'CAS Uploads', meta: '6 statements', color: 'text-cyan' },
    { icon: '💰', name: 'Capital Gains', meta: 'FY 2025-26', color: 'text-orange' },
    { icon: '📋', name: 'Account Statements', meta: 'Monthly', color: 'text-teal' },
    { icon: '🧾', name: 'Tax Reports', meta: 'FY 2024-25, 25-26', color: 'text-pink' },
  ];

  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <Card>
        <CardHeader>
          <CardTitle>Document vault</CardTitle>
          <CardDescription>
            All your KYC, consent, tax and statement documents — preview, replace, download or view
            version history
          </CardDescription>
        </CardHeader>
        <CardBody>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {docs.map((doc) => (
              <div key={doc.name} className="flex flex-col gap-3 rounded-lg border border-line p-4">
                <div className="flex items-center gap-3">
                  <span className={cn('text-h4', doc.color)}>{doc.icon}</span>
                  <div className="flex-1">
                    <div className="text-small font-bold text-ink">{doc.name}</div>
                    <div className="text-caption text-ink-muted">{doc.meta}</div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="flex-1">
                    Preview
                  </Button>
                  <Button variant="outline" size="sm" className="flex-1">
                    Download
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

function SecurityPanel() {
  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Security score</CardTitle>
            <CardDescription>Your account protection level</CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-8 border-emerald/20 bg-emerald/10">
                <div className="text-h3 font-bold text-emerald">86</div>
              </div>
              <div className="flex-1">
                <div className="text-body font-medium text-ink">Strong protection</div>
                <div className="text-caption text-ink-muted">
                  2FA and biometric are on. Add a passkey and a recovery phone to reach 100.
                </div>
              </div>
            </div>

            {[
              ['Two-Factor Authentication', 'Authenticator app', true],
              ['Biometric Login', 'Face ID on this device', true],
              ['Passkeys', 'Not set up', false],
              ['Recovery Email', 'aarav.s@example.com', true],
              ['Recovery Phone', 'Not added', false],
            ].map(([title, desc, on], idx) => (
              <div key={idx} className="flex items-center justify-between gap-3 border-b border-line py-3 last:border-b-0 last:py-0">
                <div>
                  <div className="text-body font-medium text-ink">{title}</div>
                  <div className="text-caption text-ink-muted">{desc}</div>
                </div>
                {on ? (
                  <span className="rounded bg-emerald/10 px-2 py-1 text-caption font-bold text-emerald">
                    On
                  </span>
                ) : (
                  <Button variant="outline" size="sm">
                    Set up
                  </Button>
                )}
              </div>
            ))}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Devices &amp; sessions</CardTitle>
            <CardDescription>Where you&apos;re signed in</CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            {[
              { icon: '💻', name: 'MacBook Pro · Gurugram', meta: 'Active now · Chrome', current: true },
              { icon: '📱', name: 'iPhone 15 · Gurugram', meta: '2 hours ago · DhanRadar app', current: false },
              { icon: '💻', name: 'Windows PC · Mumbai', meta: '3 days ago · Edge', current: false },
            ].map((device, idx) => (
              <div key={idx} className="flex items-center gap-3 border-b border-line pb-3 last:border-b-0 last:pb-0">
                <span className="text-h4">{device.icon}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-body font-medium text-ink">
                    {device.name}
                    {device.current && (
                      <span className="rounded bg-emerald/10 px-2 py-0.5 text-caption font-bold text-emerald">
                        This device
                      </span>
                    )}
                  </div>
                  <div className="text-caption text-ink-muted">{device.meta}</div>
                </div>
                {!device.current && (
                  <Button variant="outline" size="sm">
                    Log out
                  </Button>
                )}
              </div>
            ))}
            <Button variant="danger" className="mt-2 w-full">
              Log Out All Devices
            </Button>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function NotificationsPanel() {
  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Channels</CardTitle>
            <CardDescription>How we reach you</CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-4">
            {[
              ['Email', 'aarav.s@example.com', true],
              ['Push', 'iPhone app', true],
              ['SMS', '+91 98765 ••210', true],
              ['WhatsApp', '+91 98765 ••210', true],
            ].map(([title, desc, on], idx) => (
              <div key={idx} className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-body font-medium text-ink">{title}</div>
                  <div className="text-caption text-ink-muted">{desc}</div>
                </div>
                <Toggle
                  id={`channel-${idx}`}
                  checked={on as boolean}
                  onChange={() => {}}
                  disabled
                  label={`Toggle ${title}`}
                />
              </div>
            ))}
            <FieldRow label="Digest" value="Daily 8:00 AM" action={<Button variant="outline" size="sm">Change</Button>} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Alert types</CardTitle>
            <CardDescription>What matters to you</CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-4">
            {[
              ['Portfolio alerts', 'Score changes, rebalancing', true],
              ['SIP alerts', 'Debits & confirmations', true],
              ['NAV alerts', 'Daily watchlist NAVs', false],
              ['Goal alerts', 'Progress & milestones', true],
              ['Market alerts', 'DMMI shifts, big moves', true],
              ['Research updates', 'New analysis & rankings', true],
              ['AI reports', 'Weekly commentary', true],
            ].map(([title, desc, on], idx) => (
              <div key={idx} className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-body font-medium text-ink">{title}</div>
                  <div className="text-caption text-ink-muted">{desc}</div>
                </div>
                <Toggle
                  id={`alert-${idx}`}
                  checked={on as boolean}
                  onChange={() => {}}
                  disabled
                  label={`Toggle ${title}`}
                />
              </div>
            ))}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function PreferencesPanel() {
  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Display</CardTitle>
            <CardDescription>Look &amp; feel</CardDescription>
          </CardHeader>
          <CardBody>
            <FieldRow label="Language" value="English" action={<Button variant="outline" size="sm">Change</Button>} />
            <FieldRow label="Currency" value="₹ INR" action={<Button variant="outline" size="sm">Change</Button>} />
            <FieldRow label="Theme" value="Light" action={<Button variant="outline" size="sm">Change</Button>} />
            <FieldRow label="Accessibility" value="Standard" action={<Button variant="outline" size="sm">Adjust</Button>} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Defaults</CardTitle>
            <CardDescription>Your starting views</CardDescription>
          </CardHeader>
          <CardBody>
            <FieldRow label="Homepage" value="Dashboard" action={<Button variant="outline" size="sm">Change</Button>} />
            <FieldRow label="Portfolio" value="By value" action={<Button variant="outline" size="sm">Change</Button>} />
            <FieldRow label="Returns" value="XIRR" action={<Button variant="outline" size="sm">Change</Button>} />
            <FieldRow label="Benchmark" value="NIFTY 50" action={<Button variant="outline" size="sm">Change</Button>} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Tools</CardTitle>
            <CardDescription>Calculator &amp; filters</CardDescription>
          </CardHeader>
          <CardBody>
            <FieldRow label="Default SIP" value={<code className="font-mono">₹25,000</code>} />
            <FieldRow label="Fund Filters" value="Score ≥ 75" action={<Button variant="outline" size="sm">Edit</Button>} />
            <FieldRow label="Widgets" value="6 active" action={<Button variant="outline" size="sm">Set</Button>} />
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function ConnectedPanel() {
  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <Card>
        <CardHeader>
          <CardTitle>Connected accounts</CardTitle>
          <CardDescription>Monitor health &amp; reconnect anytime</CardDescription>
        </CardHeader>
        <CardBody className="flex flex-col gap-3">
          {[
            { logo: 'B', color: '#00518F', name: 'Portfolio Sync', meta: 'Synced 2h', health: 'Healthy' },
            { logo: 'C', color: '#E2761B', name: 'CAMS', meta: 'Synced 2h', health: 'Healthy' },
            { logo: 'M', color: '#1A7F5A', name: 'MF Central', meta: 'Synced 1d', health: 'Healthy' },
            { logo: '✉', color: '#EA4335', name: 'Email Import', meta: '3d ago', health: 'Active' },
            { logo: 'D', color: '#1565C0', name: 'DigiLocker', meta: 'KYC synced', health: 'Connected' },
            { logo: 'K', color: '#7B2D8E', name: 'KFintech', meta: 'Reconnect', health: 'Off' },
          ].map((acc, idx) => (
            <div key={idx} className="flex items-center gap-3 border-b border-line pb-3 last:border-b-0 last:pb-0">
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-body font-bold text-white"
                style={{ backgroundColor: acc.color }}
              >
                {acc.logo}
              </div>
              <div className="flex-1">
                <div className="text-body font-bold text-ink">{acc.name}</div>
                <div className="text-caption text-ink-muted">{acc.meta}</div>
              </div>
              <span
                className={cn(
                  'flex items-center gap-1.5 text-caption font-medium',
                  acc.health === 'Off' ? 'text-ink-muted' : 'text-emerald',
                )}
              >
                <span
                  className={cn(
                    'h-2 w-2 rounded-full',
                    acc.health === 'Off' ? 'bg-ink-muted' : 'bg-emerald',
                  )}
                />
                {acc.health}
              </span>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}

function ActivityPanel() {
  const activities = [
    { time: 'Today 4:32 PM', title: 'Portfolio synced', desc: '5 accounts · 9 funds', color: 'bg-emerald', icon: '↻' },
    { time: 'Today 9:01 AM', title: 'Logged in', desc: 'MacBook · Gurugram', color: 'bg-royal', icon: '→' },
    { time: 'Yesterday', title: 'AI summary', desc: 'Weekly commentary', color: 'bg-violet', icon: '✦' },
    { time: '2 days ago', title: 'CAS uploaded', desc: 'June 2026', color: 'bg-emerald', icon: '⬆' },
    { time: '5 days ago', title: 'Consent updated', desc: 'WhatsApp enabled', color: 'bg-amber', icon: '🔐' },
    { time: '12 Mar 2026', title: 'Risk completed', desc: 'Score 68', color: 'bg-orange', icon: '🎯' },
    { time: 'Mar 2025', title: 'Account created', desc: 'Welcome', color: 'bg-navy', icon: '★' },
  ];

  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <Card>
        <CardHeader>
          <CardTitle>Activity history</CardTitle>
          <CardDescription>Everything on your account</CardDescription>
        </CardHeader>
        <CardBody>
          <div className="relative border-l-2 border-line pl-6">
            {activities.map((act, idx) => (
              <div key={idx} className="relative pb-6 last:pb-0">
                <div
                  className={cn(
                    'absolute -left-[28px] top-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 border-surface text-caption font-bold text-white',
                    act.color,
                  )}
                >
                  {act.icon}
                </div>
                <div className="font-mono text-caption text-ink-muted">{act.time}</div>
                <div className="mt-0.5 text-body font-bold text-ink">{act.title}</div>
                <div className="text-caption text-ink-muted">{act.desc}</div>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

function DataPrivacyPanel() {
  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Export your data</CardTitle>
            <CardDescription>Download everything we hold about you</CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            {[
              ['Profile & KYC', 'Personal details, verification'],
              ['Portfolio data', 'Holdings, transactions, CAS'],
              ['Goals & watchlists', 'Your saved plans and lists'],
              ['Documents', 'All vault files'],
              ['AI & search history', 'Your queries and reports'],
            ].map(([title, desc], idx) => (
              <div key={idx} className="flex items-center justify-between gap-3 border-b border-line pb-3 last:border-b-0 last:pb-0">
                <div className="flex-1">
                  <div className="text-body font-medium text-ink">{title}</div>
                  <div className="text-caption text-ink-muted">{desc}</div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm">
                    JSON
                  </Button>
                  <Button variant="outline" size="sm">
                    PDF
                  </Button>
                </div>
              </div>
            ))}
            <Button variant="primary" className="mt-2 w-full">
              📦 Export Everything
            </Button>
          </CardBody>
        </Card>

        <Card className="border-red/30 bg-red/5">
          <CardHeader>
            <CardTitle className="text-red">Delete data</CardTitle>
            <CardDescription>Permanent &amp; irreversible</CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            {['Uploaded CAS', 'Portfolio data', 'Goals', 'Watchlists', 'AI history'].map((item) => (
              <div key={item} className="flex items-center justify-between gap-3 border-b border-red/15 pb-3 last:border-b-0 last:pb-0">
                <div className="text-body font-medium text-ink">{item}</div>
                <Button variant="danger" size="sm">
                  Delete
                </Button>
              </div>
            ))}
            <div className="mt-2 rounded-lg border border-red/25 bg-red/10 p-4">
              <div className="text-body font-bold text-red">⚠ Delete entire account</div>
              <div className="mt-1 text-caption text-ink-secondary">
                Requires multiple confirmations &amp; a 14-day cooling-off period.
              </div>
              <Button variant="danger" className="mt-3 w-full">
                Delete My Account
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function SupportPanel() {
  return (
    <div className="flex flex-col gap-4">
      <IllustrativeBadge />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Your relationship manager</CardTitle>
            <CardDescription>Pro members get priority support</CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-royal to-emerald text-body font-bold text-white">
                PK
              </div>
              <div>
                <div className="text-body font-bold text-ink">Priya Krishnan</div>
                <div className="text-caption text-ink-muted">Senior RM · within 4 hours</div>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="primary" className="flex-1">
                💬 Chat
              </Button>
              <Button variant="outline">📞</Button>
              <Button variant="outline">✉</Button>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Help &amp; tickets</CardTitle>
            <CardDescription>Answers or raise an issue</CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-2">
            {[
              { icon: '🎫', name: 'Support tickets', meta: '2 open' },
              { icon: '⚠', name: 'Raise complaint', meta: 'Grievance officer' },
              { icon: '❓', name: 'FAQs', meta: '200+ articles' },
              { icon: '📋', name: 'Regulatory info', meta: 'SEBI, AMFI' },
              { icon: '📞', name: 'Contact', meta: '24×7 helpline' },
            ].map((item, idx) => (
              <button
                key={idx}
                className="flex items-center gap-3 rounded-lg border border-line p-3 text-left transition-colors hover:border-royal hover:bg-royal/5"
              >
                <span className="text-h5">{item.icon}</span>
                <div className="flex-1">
                  <div className="text-body font-medium text-ink">{item.name}</div>
                  <div className="text-caption text-ink-muted">{item.meta}</div>
                </div>
                <span className="text-ink-faint">›</span>
              </button>
            ))}
          </CardBody>
        </Card>
      </div>

      <div className="mt-2">
        <div className="mb-3 flex items-center gap-2">
          <h3 className="text-body font-bold text-ink">Coming soon</h3>
          <span className="rounded-full bg-violet/10 px-2 py-0.5 text-caption font-bold uppercase tracking-wide text-violet">
            Future
          </span>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: '👨‍👩‍👧', name: 'Family' },
            { icon: '🤝', name: 'Joint' },
            { icon: '🧒', name: 'Minor A/C' },
            { icon: '🏛', name: 'HUF/Trust' },
            { icon: '🛡', name: 'Insurance' },
            { icon: '🏦', name: 'Loans' },
            { icon: '🧾', name: 'Tax Filing' },
            { icon: '💚', name: 'Wellness' },
          ].map((item) => (
            <div
              key={item.name}
              className="flex items-center gap-3 rounded-lg border border-dashed border-line bg-surface-2 p-3 opacity-80"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-line bg-surface text-body">
                {item.icon}
              </div>
              <div className="flex-1">
                <div className="text-small font-bold text-ink">{item.name}</div>
                <div className="font-mono text-[9px] font-bold uppercase tracking-wide text-violet">
                  Planned
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------
export default function ProfilePage() {
  const { data: me, isLoading: meLoading } = useMe();
  const [activeTab, setActiveTab] = React.useState<TabId>('overview');
  const tabsRef = React.useRef<HTMLDivElement>(null);

  // Scroll active tab into view when it changes
  React.useEffect(() => {
    if (!tabsRef.current) return;
    const activeButton = tabsRef.current.querySelector('[aria-current="page"]');
    if (activeButton && typeof activeButton.scrollIntoView === 'function') {
      activeButton.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
  }, [activeTab]);

  if (meLoading || !me) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1">
          <Skeleton className="h-8 w-64 rounded-md" />
          <Skeleton className="h-4 w-96 rounded-md" />
        </div>
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Page header */}
      <div className="flex flex-col gap-1">
        <h1 className="text-h2 text-ink">Customer Profile</h1>
        <p className="text-small text-ink-secondary">
          Manage your account, investment profile, security, privacy and preferences from one place.
        </p>
      </div>

      {/* Profile hero */}
      <ProfileHero email={me.email} tier={me.tier} />

      {/* Tab navigation */}
      <div className="sticky top-14 z-20 -mx-6 border-b border-line bg-surface/95 px-6 backdrop-blur-sm">
        <div
          ref={tabsRef}
          className="flex gap-1 overflow-x-auto pb-2 pt-3 scrollbar-none"
          role="tablist"
          aria-label="Profile sections"
        >
          {TABS.map((tab) => (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-current={activeTab === tab.id ? 'page' : undefined}
              aria-controls={`panel-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'shrink-0 whitespace-nowrap rounded-lg border px-4 py-2 text-small font-medium transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                activeTab === tab.id
                  ? 'border-navy bg-navy text-white'
                  : 'border-line bg-surface text-ink-secondary hover:border-line-strong hover:text-ink',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab panels */}
      <div className="pb-12">
        {activeTab === 'overview' && (
          <div id="panel-overview" role="tabpanel" aria-labelledby="tab-overview">
            <OverviewPanel />
          </div>
        )}
        {activeTab === 'personal' && (
          <div id="panel-personal" role="tabpanel" aria-labelledby="tab-personal">
            <PersonalPanel />
          </div>
        )}
        {activeTab === 'investment' && (
          <div id="panel-investment" role="tabpanel" aria-labelledby="tab-investment">
            <InvestmentPanel />
          </div>
        )}
        {activeTab === 'risk' && (
          <div id="panel-risk" role="tabpanel" aria-labelledby="tab-risk">
            <RiskPanel />
          </div>
        )}
        {activeTab === 'privacy' && (
          <div id="panel-privacy" role="tabpanel" aria-labelledby="tab-privacy">
            <PrivacyPanel />
          </div>
        )}
        {activeTab === 'accounts' && (
          <div id="panel-accounts" role="tabpanel" aria-labelledby="tab-accounts">
            <AccountsPanel />
          </div>
        )}
        {activeTab === 'documents' && (
          <div id="panel-documents" role="tabpanel" aria-labelledby="tab-documents">
            <DocumentsPanel />
          </div>
        )}
        {activeTab === 'security' && (
          <div id="panel-security" role="tabpanel" aria-labelledby="tab-security">
            <SecurityPanel />
          </div>
        )}
        {activeTab === 'notifications' && (
          <div id="panel-notifications" role="tabpanel" aria-labelledby="tab-notifications">
            <NotificationsPanel />
          </div>
        )}
        {activeTab === 'preferences' && (
          <div id="panel-preferences" role="tabpanel" aria-labelledby="tab-preferences">
            <PreferencesPanel />
          </div>
        )}
        {activeTab === 'connected' && (
          <div id="panel-connected" role="tabpanel" aria-labelledby="tab-connected">
            <ConnectedPanel />
          </div>
        )}
        {activeTab === 'activity' && (
          <div id="panel-activity" role="tabpanel" aria-labelledby="tab-activity">
            <ActivityPanel />
          </div>
        )}
        {activeTab === 'data' && (
          <div id="panel-data" role="tabpanel" aria-labelledby="tab-data">
            <DataPrivacyPanel />
          </div>
        )}
        {activeTab === 'support' && (
          <div id="panel-support" role="tabpanel" aria-labelledby="tab-support">
            <SupportPanel />
          </div>
        )}
      </div>
    </div>
  );
}
