'use client';

/**
 * Admin BSE UAT Console — /admin/bse-uat
 *
 * Screen-share surface for the BSE StAR MF demo session: drives the READ-ONLY
 * backend proxy (/api/v1/admin/bse-uat/*) against the BSE UAT demo tenant and
 * shows our own webhook-events evidence trail. Admin-gated (404-hidden), UAT
 * tenant only, numeric values allowed (admin surface, §16). No advisory verbs.
 *
 * The BSE password is sent once to create a short-lived session token cached
 * server-side; it is never stored in the browser.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { CheckCircle2, Landmark, RefreshCw, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Input, PasswordInput } from '@/components/ui/Input';
import { api } from '@/lib/apiClient';

interface ProxyResult {
  http_status: number;
  body: unknown;
}

interface WebhookEventRow {
  event_type: string;
  event: string;
  client_code: string | null;
  order_id: string | null;
  received_at: string | null;
  processed_at: string | null;
}

function Raw({ data }: { data: unknown }) {
  return (
    <pre className="mt-2 max-h-72 overflow-auto rounded-md bg-surface-2 p-3 text-xs leading-relaxed">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ' +
        (ok ? 'bg-emerald/10 text-emerald' : 'bg-red/5 text-red')
      }
    >
      {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
      {label}
    </span>
  );
}

export default function BseUatConsolePage() {
  // --- session ---
  const [password, setPassword] = React.useState('');
  const [sessionActive, setSessionActive] = React.useState<boolean | null>(null);
  const [sessionBusy, setSessionBusy] = React.useState(false);
  const [sessionErr, setSessionErr] = React.useState<string | null>(null);

  const refreshSession = React.useCallback(async () => {
    try {
      const s = await api.get<{ active: boolean }>('/admin/bse-uat/session');
      setSessionActive(s.active);
    } catch {
      setSessionActive(false);
    }
  }, []);
  React.useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  async function login() {
    setSessionBusy(true);
    setSessionErr(null);
    try {
      await api.post('/admin/bse-uat/session', { password });
      setPassword('');
      setSessionActive(true);
    } catch (e) {
      setSessionErr(e instanceof Error ? e.message : 'Login failed');
      setSessionActive(false);
    } finally {
      setSessionBusy(false);
    }
  }

  // --- generic proxy caller ---
  const [results, setResults] = React.useState<Record<string, ProxyResult | null>>({});
  const [busy, setBusy] = React.useState<Record<string, boolean>>({});
  const [errs, setErrs] = React.useState<Record<string, string | null>>({});

  async function callProxy(key: string, path: string) {
    setBusy((b) => ({ ...b, [key]: true }));
    setErrs((x) => ({ ...x, [key]: null }));
    try {
      const r = await api.get<ProxyResult>(path);
      setResults((res) => ({ ...res, [key]: r }));
    } catch (e) {
      setErrs((x) => ({ ...x, [key]: e instanceof Error ? e.message : 'Request failed' }));
    } finally {
      setBusy((b) => ({ ...b, [key]: false }));
    }
  }

  const [ucc, setUcc] = React.useState('DRTEST009');
  const [orderId, setOrderId] = React.useState('5001192870');

  // --- webhook events (no BSE session needed — our own DB) ---
  const [events, setEvents] = React.useState<WebhookEventRow[] | null>(null);
  const loadEvents = React.useCallback(async () => {
    try {
      setEvents(await api.get<WebhookEventRow[]>('/admin/bse-uat/webhook-events?limit=50'));
    } catch {
      setEvents([]);
    }
  }, []);
  React.useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  // UCC highlights extracted for the demo narrative (raw JSON stays available)
  const uccBody = (results['ucc']?.body ?? null) as {
    data?: { ucc_status?: string; ucc_status_object?: Record<string, unknown> };
  } | null;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Landmark className="h-6 w-6 text-royal" />
        <div>
          <h1 className="text-xl font-semibold">BSE UAT Console</h1>
          <p className="text-sm text-ink-muted">
            Read-only view of the BSE StAR MF 2.0 UAT demo tenant (member 66910). UAT only — this
            console cannot reach the production BSE gateway.
          </p>
        </div>
      </div>

      {/* Session */}
      <Card>
        <CardHeader>
          <CardTitle>UAT session</CardTitle>
          {sessionActive !== null && (
            <StatusPill ok={!!sessionActive} label={sessionActive ? 'Session active' : 'No session'} />
          )}
        </CardHeader>
        <CardBody>
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-72">
              <PasswordInput
                placeholder="BSE member password (never stored)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <Button onClick={login} disabled={sessionBusy || !password}>
              {sessionBusy ? 'Logging in…' : 'Login to BSE UAT'}
            </Button>
            <Button variant="secondary" onClick={refreshSession}>
              <RefreshCw className="mr-1 h-4 w-4" /> Check session
            </Button>
          </div>
          <p className="mt-2 text-xs text-ink-muted">
            One login attempt per click — a wrong password counts toward BSE&apos;s member lockout.
          </p>
          {sessionErr && <p className="mt-2 text-sm text-red">{sessionErr}</p>}
        </CardBody>
      </Card>

      {/* UCC */}
      <Card>
        <CardHeader>
          <CardTitle>UCC status (get_ucc)</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-56">
              <Input value={ucc} onChange={(e) => setUcc(e.target.value)} placeholder="Client code" />
            </div>
            <Button onClick={() => callProxy('ucc', `/admin/bse-uat/ucc/${encodeURIComponent(ucc)}`)} disabled={!!busy['ucc']}>
              {busy['ucc'] ? 'Fetching…' : 'Fetch UCC'}
            </Button>
          </div>
          {errs['ucc'] && <p className="mt-2 text-sm text-red">{errs['ucc']}</p>}
          {uccBody?.data && (
            <div className="mt-3 flex flex-wrap gap-2">
              <StatusPill
                ok={uccBody.data.ucc_status === 'ACTIVE'}
                label={`ucc_status: ${uccBody.data.ucc_status ?? 'unknown'}`}
              />
            </div>
          )}
          {results['ucc'] && <Raw data={results['ucc']} />}
        </CardBody>
      </Card>

      {/* Orders */}
      <Card>
        <CardHeader>
          <CardTitle>Orders (order_get / order_list)</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-56">
              <Input value={orderId} onChange={(e) => setOrderId(e.target.value)} placeholder="Order id" />
            </div>
            <Button
              onClick={() => callProxy('order', `/admin/bse-uat/order/${encodeURIComponent(orderId)}`)}
              disabled={!!busy['order']}
            >
              {busy['order'] ? 'Fetching…' : 'Fetch order'}
            </Button>
            <Button variant="secondary" onClick={() => callProxy('orders', '/admin/bse-uat/orders')} disabled={!!busy['orders']}>
              {busy['orders'] ? 'Fetching…' : 'List all orders'}
            </Button>
          </div>
          {errs['order'] && <p className="mt-2 text-sm text-red">{errs['order']}</p>}
          {errs['orders'] && <p className="mt-2 text-sm text-red">{errs['orders']}</p>}
          {results['order'] && <Raw data={results['order']} />}
          {results['orders'] && <Raw data={results['orders']} />}
        </CardBody>
      </Card>

      {/* Mandates */}
      <Card>
        <CardHeader>
          <CardTitle>Mandates (mandate_list)</CardTitle>
        </CardHeader>
        <CardBody>
          <Button
            onClick={() => callProxy('mandates', `/admin/bse-uat/mandates?ucc=${encodeURIComponent(ucc)}`)}
            disabled={!!busy['mandates']}
          >
            {busy['mandates'] ? 'Fetching…' : `List mandates for ${ucc}`}
          </Button>
          <p className="mt-2 text-xs text-ink-muted">
            Expected 0 on the demo tenant — bank verification is the open environment item with BSE
            (mandates, SXP and redemption payout gate on a verified bank).
          </p>
          {errs['mandates'] && <p className="mt-2 text-sm text-red">{errs['mandates']}</p>}
          {results['mandates'] && <Raw data={results['mandates']} />}
        </CardBody>
      </Card>

      {/* Webhook evidence */}
      <Card>
        <CardHeader>
          <CardTitle>Webhook events received (our inbox)</CardTitle>
          <Button variant="secondary" onClick={loadEvents}>
            <RefreshCw className="mr-1 h-4 w-4" /> Refresh
          </Button>
        </CardHeader>
        <CardBody>
          {events === null ? (
            <p className="text-sm text-ink-muted">Loading…</p>
          ) : events.length === 0 ? (
            <EmptyState title="No webhook events" description="No BSE webhook events recorded yet." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase text-ink-muted">
                    <th className="py-2 pr-4">Module</th>
                    <th className="py-2 pr-4">Event</th>
                    <th className="py-2 pr-4">Client</th>
                    <th className="py-2 pr-4">Order</th>
                    <th className="py-2 pr-4">Received</th>
                    <th className="py-2">Processed</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e, i) => (
                    <tr key={i} className="border-b border-line/50">
                      <td className="py-1.5 pr-4">{e.event_type}</td>
                      <td className="py-1.5 pr-4 font-mono text-xs">{e.event}</td>
                      <td className="py-1.5 pr-4">{e.client_code ?? '—'}</td>
                      <td className="py-1.5 pr-4">{e.order_id ?? '—'}</td>
                      <td className="py-1.5 pr-4 whitespace-nowrap">
                        {e.received_at ? new Date(e.received_at).toLocaleString() : '—'}
                      </td>
                      <td className="py-1.5">
                        {e.processed_at ? new Date(e.processed_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
