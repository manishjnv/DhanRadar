'use client';

/**
 * Admin MF Utility UAT Console — /admin/mfu-uat
 *
 * Screen-share surface for the MF Utility (MFU) test system (test.mfuonline.com):
 * status checklist, one-click login, and the raw call log. Mirrors
 * /admin/bse-uat's shape (RequireAdmin, 404-surface-hiding). Also carries the
 * BSE-vs-MFU provider switch card, whose backend (/admin/mf-txn/provider)
 * ships on a parallel branch — this page degrades to "not available yet" if
 * that route 404s.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { CheckCircle2, ChevronDown, ChevronRight, Landmark, RefreshCw, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { api, ApiError } from '@/lib/apiClient';

// ---------------------------------------------------------------------------
// Contract types
// ---------------------------------------------------------------------------
interface PingResp {
  enabled: boolean;
  base_url_ok: boolean;
  configured: {
    entity_id: boolean;
    login_user: boolean;
    login_password: boolean;
    aes_key: boolean;
    aes_iv: boolean;
  };
  token_cached: boolean;
  token_ttl_s: number | null;
  cooldown_s: number | null;
}

interface ApiLogRow {
  unique_id: string;
  api_type: string;
  created_at: string | null;
  http_status: number | null;
  resp_flag: 'S' | 'F' | null;
  error_code: string | null;
  error_msg: string | null;
  latency_ms: number | null;
  request_json: unknown;
  response_json: unknown;
}

interface ProviderOption {
  id: 'bse' | 'mfu';
  label: string;
  ready: boolean;
  note: string;
}

interface ProviderResp {
  provider: 'bse' | 'mfu';
  provider_label: string;
  source: 'override' | 'default';
  default: string;
  options: ProviderOption[];
}

// ---------------------------------------------------------------------------
// Humanizers
// ---------------------------------------------------------------------------
const LOGIN_ERROR_COPY: Record<string, string> = {
  DISABLED: 'MF Utility is switched off on the server.',
  NOT_CONFIGURED: 'MF Utility settings are missing on the server.',
  NOT_UAT_HOST: "Not pointing at MF Utility's test system.",
  COOLDOWN: 'The last login failed. Please wait a few minutes (safety rule).',
  LOGIN_IN_FLIGHT: 'Another login is already running.',
  TRANSPORT_ERROR: 'Could not reach MF Utility.',
};

function humanizeLoginError(err: unknown): string {
  if (err instanceof ApiError) {
    const code = typeof err.problem.error_code === 'string' ? err.problem.error_code : undefined;
    const msg = typeof err.problem.error_msg === 'string' ? err.problem.error_msg : err.problem.detail;
    if (code && LOGIN_ERROR_COPY[code]) return LOGIN_ERROR_COPY[code];
    if (code) return `MF Utility replied: ${code} — ${msg ?? 'unknown error'}`;
    return err.problem.detail ?? err.message;
  }
  return err instanceof Error ? err.message : 'Login failed.';
}

function humanizeApiType(apiType: string): string {
  if (apiType === 'OAUTH-LOGIN') return 'Login';
  return apiType
    .toLowerCase()
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatTimeIST(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const date = d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', timeZone: 'Asia/Kolkata' });
  const time = d.toLocaleTimeString('en-IN', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'Asia/Kolkata',
  });
  return `${date}, ${time}`;
}

function formatLatency(ms: number | null): string {
  if (ms === null) return '—';
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
}

function formatTtl(ttlS: number | null): string {
  if (!ttlS || ttlS <= 0) return 'no';
  const hours = ttlS / 3600;
  if (hours >= 1) return `yes — ${hours.toFixed(0)} h left`;
  const minutes = Math.max(1, Math.round(ttlS / 60));
  return `yes — ${minutes} min left`;
}

function formatCooldown(cooldownS: number | null): string {
  if (!cooldownS || cooldownS <= 0) return 'none';
  const minutes = Math.max(1, Math.round(cooldownS / 60));
  return `wait ${minutes} min`;
}

// ---------------------------------------------------------------------------
// Small pieces
// ---------------------------------------------------------------------------
function CheckRow({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className="flex items-center gap-2 py-1 text-sm text-ink">
      {ok ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald" aria-hidden="true" />
      ) : (
        <XCircle className="h-4 w-4 shrink-0 text-red" aria-hidden="true" />
      )}
      <span>{label}</span>
    </li>
  );
}

function ResultPill({ ok }: { ok: boolean }) {
  return (
    <span
      className={
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ' +
        (ok ? 'bg-emerald/10 text-emerald' : 'bg-red/5 text-red')
      }
    >
      {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
      {ok ? 'Success' : 'Failed'}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function MfuUatConsolePage() {
  // --- status (ping) ---
  const [ping, setPing] = React.useState<PingResp | null>(null);
  const [pingBusy, setPingBusy] = React.useState(false);
  const [pingErr, setPingErr] = React.useState<string | null>(null);

  const refreshPing = React.useCallback(async () => {
    setPingBusy(true);
    setPingErr(null);
    try {
      setPing(await api.get<PingResp>('/admin/mfu-uat/ping'));
    } catch (e) {
      setPingErr(e instanceof Error ? e.message : 'Could not load status. Refresh to try again.');
    } finally {
      setPingBusy(false);
    }
  }, []);

  // --- call log ---
  const [logRows, setLogRows] = React.useState<ApiLogRow[] | null>(null);
  const [logErr, setLogErr] = React.useState<string | null>(null);
  const [expanded, setExpanded] = React.useState<string | null>(null);

  const refreshLog = React.useCallback(async () => {
    setLogErr(null);
    try {
      setLogRows(await api.get<ApiLogRow[]>('/admin/mfu-uat/api-log?limit=50'));
    } catch (e) {
      setLogErr(e instanceof Error ? e.message : 'Could not load the call log. Refresh to try again.');
      setLogRows([]);
    }
  }, []);

  React.useEffect(() => {
    void refreshPing();
    void refreshLog();
  }, [refreshPing, refreshLog]);

  // --- login ---
  const [loginBusy, setLoginBusy] = React.useState(false);
  const [loginErr, setLoginErr] = React.useState<string | null>(null);
  const [loginOk, setLoginOk] = React.useState<string | null>(null);

  async function login() {
    setLoginBusy(true);
    setLoginErr(null);
    setLoginOk(null);
    try {
      const r = await api.post<{ ok: boolean; ttl_s: number }>('/admin/mfu-uat/session');
      const hours = (r.ttl_s / 3600).toFixed(1);
      setLoginOk(`Logged in — valid for ${hours} hours.`);
    } catch (e) {
      setLoginErr(humanizeLoginError(e));
    } finally {
      setLoginBusy(false);
      void refreshPing();
      void refreshLog();
    }
  }

  // --- provider switch (parallel-branch endpoint; may not exist yet) ---
  const [provider, setProvider] = React.useState<ProviderResp | null>(null);
  const [providerUnavailable, setProviderUnavailable] = React.useState(false);
  const [providerBusy, setProviderBusy] = React.useState(false);
  const [confirmTarget, setConfirmTarget] = React.useState<'bse' | 'mfu' | 'default' | null>(null);

  const refreshProvider = React.useCallback(async () => {
    try {
      setProvider(await api.get<ProviderResp>('/admin/mf-txn/provider'));
      setProviderUnavailable(false);
    } catch {
      // 404 (not deployed yet) or any other failure — same friendly fallback.
      setProviderUnavailable(true);
    }
  }, []);

  React.useEffect(() => {
    void refreshProvider();
  }, [refreshProvider]);

  async function switchProvider() {
    if (!confirmTarget) return;
    setProviderBusy(true);
    try {
      const body = { provider: confirmTarget === 'default' ? null : confirmTarget };
      const r = await api.putH<ProviderResp>('/admin/mf-txn/provider', body, {
        'Idempotency-Key': crypto.randomUUID(),
      });
      setProvider(r);
    } finally {
      setProviderBusy(false);
    }
  }

  return (
    <div className="min-w-0 space-y-6">
      <div className="flex items-center gap-2">
        <Landmark className="h-6 w-6 text-royal" />
        <div>
          <h1 className="text-xl font-semibold">MF Utility UAT Console</h1>
          <p className="text-sm text-ink-muted">Test system only (test.mfuonline.com). Admin only.</p>
        </div>
      </div>

      {/* Provider switch */}
      <Card>
        <CardHeader>
          <CardTitle>Which provider takes new orders</CardTitle>
        </CardHeader>
        <CardBody>
          {providerUnavailable ? (
            <p className="text-sm text-ink-muted">Provider switch not available yet.</p>
          ) : !provider ? (
            <p className="text-sm text-ink-muted">Loading…</p>
          ) : (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-ink">
                Current: <span className="font-medium">{provider.provider_label}</span>{' '}
                <span className="text-ink-muted">
                  ({provider.source === 'override' ? 'set by admin' : 'default'})
                </span>
              </p>
              <div className="flex flex-wrap gap-3">
                {provider.options.map((opt) => {
                  const isCurrent = opt.id === provider.provider;
                  return (
                    <div key={opt.id} className="flex flex-col gap-1">
                      <Button
                        variant={isCurrent ? 'secondary' : 'primary'}
                        disabled={isCurrent || !opt.ready}
                        onClick={() => setConfirmTarget(opt.id)}
                      >
                        {isCurrent ? `Current: ${opt.label}` : `Use ${opt.label}`}
                      </Button>
                      {!opt.ready && opt.note && (
                        <p className="max-w-[16rem] text-xs text-ink-muted">{opt.note}</p>
                      )}
                    </div>
                  );
                })}
              </div>
              {provider.source === 'override' && (
                <Button variant="ghost" onClick={() => setConfirmTarget('default')} className="w-fit">
                  Reset to default
                </Button>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      <ConfirmDialog
        open={!!confirmTarget}
        onClose={() => setConfirmTarget(null)}
        title="Change order provider"
        description={
          confirmTarget === 'default'
            ? 'Reset the order provider back to the server default?'
            : `Switch new orders to ${confirmTarget === 'bse' ? 'BSE StAR MF' : 'MF Utility'}?`
        }
        confirmLabel="Confirm"
        onConfirm={async () => {
          await switchProvider();
        }}
      />

      {/* Status */}
      <Card>
        <CardHeader>
          <CardTitle>MF Utility status</CardTitle>
          <Button variant="secondary" size="sm" onClick={refreshPing} disabled={pingBusy}>
            <RefreshCw className="mr-1 h-4 w-4" /> Refresh
          </Button>
        </CardHeader>
        <CardBody>
          {pingErr && <p className="mb-2 text-sm text-red">{pingErr}</p>}
          {!ping ? (
            <p className="text-sm text-ink-muted">{pingBusy ? 'Loading…' : 'No status yet.'}</p>
          ) : (
            <ul className="divide-y divide-line/50">
              <CheckRow ok={ping.enabled} label="Switched on" />
              <CheckRow ok={ping.base_url_ok} label="Points to MFU test system" />
              <CheckRow ok={ping.configured.entity_id} label="Entity ID set" />
              <CheckRow ok={ping.configured.login_user} label="Login ID set" />
              <CheckRow ok={ping.configured.login_password} label="Password set" />
              <CheckRow ok={ping.configured.aes_key} label="Encryption key set" />
              <CheckRow ok={ping.configured.aes_iv} label="Encryption IV set" />
              <CheckRow ok={ping.token_cached} label={`Logged in — ${formatTtl(ping.token_ttl_s)}`} />
              <CheckRow ok={!ping.cooldown_s} label={`Login cooldown: ${formatCooldown(ping.cooldown_s)}`} />
            </ul>
          )}
        </CardBody>
      </Card>

      {/* Login */}
      <Card>
        <CardHeader>
          <CardTitle>Log in to MF Utility</CardTitle>
        </CardHeader>
        <CardBody>
          <Button onClick={login} disabled={loginBusy}>
            {loginBusy ? 'Logging in…' : 'Log in'}
          </Button>
          <p className="mt-2 text-xs text-ink-muted">
            One attempt per click. After a failed login, wait 5 minutes (safety rule).
          </p>
          {loginErr && <p className="mt-2 text-sm text-red">{loginErr}</p>}
          {loginOk && <p className="mt-2 text-sm text-emerald">{loginOk}</p>}
        </CardBody>
      </Card>

      {/* Call log */}
      <Card>
        <CardHeader>
          <CardTitle>MF Utility call log</CardTitle>
          <Button variant="secondary" size="sm" onClick={refreshLog}>
            <RefreshCw className="mr-1 h-4 w-4" /> Refresh
          </Button>
        </CardHeader>
        <CardBody>
          {logErr && <p className="mb-2 text-sm text-red">{logErr}</p>}
          {logRows === null ? (
            <p className="text-sm text-ink-muted">Loading…</p>
          ) : logRows.length === 0 ? (
            <EmptyState title="No MF Utility calls yet" description="Log in or run a call to see it here." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-0 text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase text-ink-muted">
                    <th scope="col" className="py-2 pr-4">Time</th>
                    <th scope="col" className="py-2 pr-4">Call</th>
                    <th scope="col" className="py-2 pr-4">Result</th>
                    <th scope="col" className="py-2 pr-4">Error</th>
                    <th scope="col" className="py-2">Time taken</th>
                  </tr>
                </thead>
                <tbody>
                  {logRows.map((row) => {
                    const ok = row.http_status === 200 && row.resp_flag !== 'F';
                    const isOpen = expanded === row.unique_id;
                    return (
                      <React.Fragment key={row.unique_id}>
                        <tr className="border-b border-line/50">
                          <td className="py-1.5 pr-4 whitespace-nowrap">
                            <button
                              type="button"
                              onClick={() => setExpanded(isOpen ? null : row.unique_id)}
                              className="inline-flex items-center gap-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
                              aria-expanded={isOpen}
                            >
                              {isOpen ? (
                                <ChevronDown className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                              ) : (
                                <ChevronRight className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                              )}
                              {formatTimeIST(row.created_at)}
                            </button>
                          </td>
                          <td className="py-1.5 pr-4">{humanizeApiType(row.api_type)}</td>
                          <td className="py-1.5 pr-4"><ResultPill ok={ok} /></td>
                          <td className="py-1.5 pr-4">
                            {row.error_code ? `${row.error_code} — ${row.error_msg ?? ''}` : '—'}
                          </td>
                          <td className="py-1.5">{formatLatency(row.latency_ms)}</td>
                        </tr>
                        {isOpen && (
                          <tr className="border-b border-line/50">
                            <td colSpan={5} className="min-w-0 bg-surface-2 px-2 py-3">
                              <div className="grid min-w-0 gap-3 md:grid-cols-2">
                                <div className="min-w-0">
                                  <p className="mb-1 text-xs font-medium text-ink-muted">Request</p>
                                  <pre className="max-h-64 min-w-0 overflow-auto rounded-md bg-surface p-3 text-xs leading-relaxed">
                                    {JSON.stringify(row.request_json, null, 2)}
                                  </pre>
                                </div>
                                <div className="min-w-0">
                                  <p className="mb-1 text-xs font-medium text-ink-muted">Response</p>
                                  <pre className="max-h-64 min-w-0 overflow-auto rounded-md bg-surface p-3 text-xs leading-relaxed">
                                    {JSON.stringify(row.response_json, null, 2)}
                                  </pre>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
