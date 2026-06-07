/**
 * MSW v2 handlers — mock data for DhanRadar launch-wedge screens.
 * All label values are non-advisory (in_form|on_track|off_track|out_of_form|insufficient_data).
 * Confidence is a band word only (high|medium|low). NO numeric DhanRadar scores.
 */
import { http, HttpResponse } from 'msw';

// ---------------------------------------------------------------------------
// Job progress counters (module-level, persists across polling calls per job)
// ---------------------------------------------------------------------------
const jobProgress: Record<string, number> = {};

function advanceProgress(jobId: string): number {
  const steps = [25, 55, 80, 100];
  const current = jobProgress[jobId] ?? 0;
  const nextIdx = steps.findIndex((s) => s > current);
  const next = nextIdx === -1 ? 100 : steps[nextIdx];
  jobProgress[jobId] = next;
  return next;
}

// ---------------------------------------------------------------------------
// Shared mock data
// ---------------------------------------------------------------------------
const SCHEMES = [
  {
    isin: 'INF179K01BB8',
    scheme_name: 'HDFC Flexi Cap Fund – Growth',
    amc_name: 'HDFC AMC',
    category: 'Flexi Cap',
    units: 142.35,
    invested: 120000,
    current_value: 148320,
    return_pct: 23.6,
    label: 'in_form',
    confidence_band: 'high',
  },
  {
    isin: 'INF200K01RO2',
    scheme_name: 'SBI Bluechip Fund – Growth',
    amc_name: 'SBI Funds Management',
    category: 'Large Cap',
    units: 88.12,
    invested: 80000,
    current_value: 91340,
    return_pct: 14.2,
    label: 'on_track',
    confidence_band: 'high',
  },
  {
    isin: 'INF846K01EW2',
    scheme_name: 'Axis Midcap Fund – Growth',
    amc_name: 'Axis AMC',
    category: 'Mid Cap',
    units: 54.78,
    invested: 50000,
    current_value: 62100,
    return_pct: 24.2,
    label: 'in_form',
    confidence_band: 'medium',
  },
  {
    isin: 'INF879O01019',
    scheme_name: 'Parag Parikh Flexi Cap Fund – Growth',
    amc_name: 'PPFAS AMC',
    category: 'Flexi Cap',
    units: 210.44,
    invested: 200000,
    current_value: 284600,
    return_pct: 42.3,
    label: 'in_form',
    confidence_band: 'high',
  },
  {
    isin: 'INF109K01Z98',
    scheme_name: 'ICICI Pru Value Discovery Fund – Growth',
    amc_name: 'ICICI Prudential AMC',
    category: 'Value',
    units: 320.90,
    invested: 150000,
    current_value: 143200,
    return_pct: -4.5,
    label: 'off_track',
    confidence_band: 'medium',
  },
  {
    isin: 'INF251K01YB2',
    scheme_name: 'Nippon India Small Cap Fund – Growth',
    amc_name: 'Nippon India AMC',
    category: 'Small Cap',
    units: 62.10,
    invested: 60000,
    current_value: 55400,
    return_pct: -7.7,
    label: 'out_of_form',
    confidence_band: 'low',
  },
  {
    isin: 'INF760K01EF1',
    scheme_name: 'Mirae Asset Large Cap Fund – Growth',
    amc_name: 'Mirae Asset AMC',
    category: 'Large Cap',
    units: 105.20,
    invested: 90000,
    current_value: 96800,
    return_pct: 7.6,
    label: 'on_track',
    confidence_band: 'medium',
  },
];

// ---------------------------------------------------------------------------
// Mock auth session. Defaults to logged-IN so `npm run dev` lands on the
// dashboard without forcing a login each reload; logout flips it false so the
// login/signup flow is still exercisable against the mock.
// ---------------------------------------------------------------------------
let mockLoggedIn = true;
const MOCK_USER = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'demo@dhanradar.in',
  tier: 'free',
  totp_verified: false,
  risk_profile: null,
  dpdp_consent_version: null,
};

const PRO_TIERS = ['pro', 'pro_plus', 'founder_lifetime'];

// ---------------------------------------------------------------------------
// Notification preferences — mutable mock state (mirrors PreferencesResponse).
// Persists across GET/POST so the settings screen round-trips realistically.
// ---------------------------------------------------------------------------
let mockPrefs: {
  telegram_chat_id: string | null;
  email_verified: boolean;
  whatsapp_number: string | null;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  channels_enabled: Record<string, boolean>;
} = {
  telegram_chat_id: null,
  email_verified: true,
  whatsapp_number: null,
  quiet_hours_start: '22:00',
  quiet_hours_end: '07:00',
  channels_enabled: { telegram: false, email: true },
};

function problem(status: number, title: string, detail?: string) {
  return HttpResponse.json(
    { type: 'about:blank', title, status, detail, request_id: `mock-${status}` },
    { status, headers: { 'Content-Type': 'application/problem+json' } },
  );
}

// ---------------------------------------------------------------------------
// Mood Compass — deterministic mock snapshot + 30-day history (no numerics).
// ---------------------------------------------------------------------------
const MOOD_SNAPSHOT = {
  snapshot_date: '2026-06-06',
  regime: 'neutral',
  confidence_band: 'medium',
  data_quality: 'ok',
  contributing_factors: [
    'NIFTY trend steady over the last 20 sessions',
    'Market breadth balanced (advances vs declines ~1:1)',
    'FII flows mildly positive through June',
  ],
  contradicting_factors: [
    'India VIX slightly elevated versus its 1-month average',
    'USD/INR firm near recent highs',
  ],
  commentary:
    'Markets are in a balanced regime — neither fearful nor euphoric. Breadth is even and volatility is moderate. This is an educational read of market sentiment, not a recommendation to act.',
  disclosure:
    'Educational market-regime read, computed twice daily from public macro and market indicators.',
  not_advice: 'This is not investment advice.',
  disclaimer_version: '2026-06-01',
};

const MOOD_HISTORY_CYCLE = [
  'fear', 'fear', 'neutral', 'neutral', 'neutral', 'greed', 'greed',
  'neutral', 'fear', 'extreme_fear', 'fear', 'neutral', 'greed', 'extreme_greed',
];

export const handlers = [
  // GET /api/v1/auth/me — 401 when anonymous (a normal state, not an error)
  http.get('/api/v1/auth/me', () => {
    if (!mockLoggedIn) {
      return HttpResponse.json(
        { type: 'about:blank', title: 'Unauthorized', status: 401, detail: 'not_authenticated', request_id: 'mock-401' },
        { status: 401, headers: { 'Content-Type': 'application/problem+json' } },
      );
    }
    return HttpResponse.json({ user: MOCK_USER });
  }),

  // POST /api/v1/auth/login
  http.post('/api/v1/auth/login', async ({ request }) => {
    const body = (await request.json().catch(() => ({}))) as { email?: string };
    mockLoggedIn = true;
    return HttpResponse.json({
      message: 'login_successful',
      user: { ...MOCK_USER, email: body.email || MOCK_USER.email },
    });
  }),

  // POST /api/v1/auth/signup
  http.post('/api/v1/auth/signup', async ({ request }) => {
    const body = (await request.json().catch(() => ({}))) as { email?: string };
    mockLoggedIn = true;
    return HttpResponse.json(
      {
        message: 'account_created',
        user: { ...MOCK_USER, email: body.email || MOCK_USER.email },
      },
      { status: 201 },
    );
  }),

  // POST /api/v1/auth/logout
  http.post('/api/v1/auth/logout', () => {
    mockLoggedIn = false;
    return HttpResponse.json({ message: 'logged_out' });
  }),

  // POST /api/v1/auth/refresh — succeeds while the mock session is live
  http.post('/api/v1/auth/refresh', () => {
    if (!mockLoggedIn) {
      return HttpResponse.json(
        { type: 'about:blank', title: 'Unauthorized', status: 401, detail: 'invalid_refresh_token', request_id: 'mock-401' },
        { status: 401, headers: { 'Content-Type': 'application/problem+json' } },
      );
    }
    return HttpResponse.json({ message: 'tokens_rotated' });
  }),

  // POST /api/v1/mf/upload/cas
  http.post('/api/v1/mf/upload/cas', async () => {
    const jobId = `job_${Math.random().toString(36).slice(2, 10)}`;
    jobProgress[jobId] = 0;
    return HttpResponse.json({ job_id: jobId, estimated_seconds: 60 });
  }),

  // GET /api/v1/mf/upload/cas/:jobId/status
  http.get('/api/v1/mf/upload/cas/:jobId/status', ({ params }) => {
    const { jobId } = params as { jobId: string };
    const progress = advanceProgress(jobId);
    const status = progress >= 100 ? 'done' : 'processing';
    return HttpResponse.json({ status, progress_pct: progress });
  }),

  // GET /api/v1/mf/portfolio/report
  http.get('/api/v1/mf/portfolio/report', () => {
    return HttpResponse.json({
      summary: {
        total_invested: 750000,
        current_value: 881760,
        xirr_pct: 18.4,
        as_of: '2026-06-04',
        scheme_count: SCHEMES.length,
      },
      schemes: SCHEMES,
      category_allocation: [
        { category: 'Flexi Cap', pct: 40 },
        { category: 'Large Cap', pct: 25 },
        { category: 'Mid Cap', pct: 10 },
        { category: 'Value', pct: 15 },
        { category: 'Small Cap', pct: 10 },
      ],
      overlap: [
        { fund_a: 'HDFC Flexi Cap Fund', fund_b: 'Parag Parikh Flexi Cap Fund', overlap_pct: 32 },
        { fund_a: 'SBI Bluechip Fund', fund_b: 'Mirae Asset Large Cap Fund', overlap_pct: 47 },
        { fund_a: 'Axis Midcap Fund', fund_b: 'Nippon India Small Cap Fund', overlap_pct: 18 },
      ],
    });
  }),

  // GET /api/v1/indices
  http.get('/api/v1/indices', () => {
    return HttpResponse.json([
      { name: 'NIFTY 50', value: 24832.65, change_pct: 0.43 },
      { name: 'SENSEX', value: 81234.78, change_pct: 0.37 },
      { name: 'NIFTY Bank', value: 53120.40, change_pct: -0.22 },
      { name: 'NIFTY Midcap 150', value: 18945.30, change_pct: 1.12 },
    ]);
  }),

  // GET /api/v1/instruments/top-scored
  http.get('/api/v1/instruments/top-scored', () => {
    return HttpResponse.json([
      { isin: 'INF879O01019', scheme_name: 'Parag Parikh Flexi Cap Fund', category: 'Flexi Cap', label: 'in_form', confidence_band: 'high' },
      { isin: 'INF179K01BB8', scheme_name: 'HDFC Flexi Cap Fund', category: 'Flexi Cap', label: 'in_form', confidence_band: 'high' },
      { isin: 'INF846K01EW2', scheme_name: 'Axis Midcap Fund', category: 'Mid Cap', label: 'in_form', confidence_band: 'medium' },
      { isin: 'INF200K01RO2', scheme_name: 'SBI Bluechip Fund', category: 'Large Cap', label: 'on_track', confidence_band: 'high' },
      { isin: 'INF760K01EF1', scheme_name: 'Mirae Asset Large Cap Fund', category: 'Large Cap', label: 'on_track', confidence_band: 'medium' },
      { isin: 'INF109K01Z98', scheme_name: 'ICICI Pru Value Discovery Fund', category: 'Value', label: 'off_track', confidence_band: 'medium' },
    ]);
  }),

  // GET /api/v1/news
  http.get('/api/v1/news', () => {
    return HttpResponse.json([
      { id: 'n1', title: 'RBI holds repo rate; MPC signals cautious outlook for FY27', source: 'Economic Times', freshness: '2h ago' },
      { id: 'n2', title: 'Midcap funds see record inflows in May 2026 at ₹9,200 Cr', source: 'Mint', freshness: '4h ago' },
      { id: 'n3', title: 'SEBI proposes stricter T+0 settlement norms for equity derivatives', source: 'Business Standard', freshness: '6h ago' },
      { id: 'n4', title: 'Flexi Cap category beats benchmark for 8th consecutive quarter', source: 'Value Research', freshness: '1d ago' },
      { id: 'n5', title: 'Foreign portfolio investors buy ₹14,000 Cr in Indian equities in June', source: 'NDTV Profit', freshness: '1d ago' },
    ]);
  }),

  // GET /api/v1/portfolio/summary — 404 cold start (empty portfolio)
  http.get('/api/v1/portfolio/summary', () => {
    return HttpResponse.json(
      { type: 'about:blank', title: 'Not Found', status: 404, request_id: 'mock-404' },
      { status: 404, headers: { 'Content-Type': 'application/problem+json' } },
    );
  }),

  // GET /api/v1/notifications/preferences (authed)
  http.get('/api/v1/notifications/preferences', () => {
    if (!mockLoggedIn) return problem(401, 'Unauthorized', 'not_authenticated');
    return HttpResponse.json(mockPrefs);
  }),

  // POST /api/v1/notifications/preferences — partial update (only sent keys)
  http.post('/api/v1/notifications/preferences', async ({ request }) => {
    if (!mockLoggedIn) return problem(401, 'Unauthorized', 'not_authenticated');
    const body = (await request.json().catch(() => ({}))) as Partial<typeof mockPrefs>;
    mockPrefs = {
      ...mockPrefs,
      ...body,
      channels_enabled: { ...mockPrefs.channels_enabled, ...(body.channels_enabled ?? {}) },
    };
    return HttpResponse.json(mockPrefs);
  }),

  // POST /api/v1/notifications/test (authed, Pro) — 402 for non-Pro, 400 if channel unset
  http.post('/api/v1/notifications/test', () => {
    if (!mockLoggedIn) return problem(401, 'Unauthorized', 'not_authenticated');
    if (!PRO_TIERS.includes(MOCK_USER.tier)) {
      return problem(402, 'Payment Required', 'tier_required');
    }
    if (!mockPrefs.telegram_chat_id) return problem(400, 'Bad Request', 'telegram_not_set');
    return HttpResponse.json({ enqueued: true, channel: 'telegram', detail: 'queued for delivery' });
  }),

  // GET /api/v1/market/mood (anonymous)
  http.get('/api/v1/market/mood', () => {
    return HttpResponse.json(MOOD_SNAPSHOT);
  }),

  // GET /api/v1/market/mood/history?days=N (anonymous)
  http.get('/api/v1/market/mood/history', ({ request }) => {
    const url = new URL(request.url);
    const days = Math.min(Math.max(Number(url.searchParams.get('days')) || 30, 1), 365);
    const base = new Date('2026-06-06T00:00:00Z');
    const items = Array.from({ length: days }, (_, i) => {
      const d = new Date(base);
      d.setUTCDate(base.getUTCDate() - (days - 1 - i));
      return {
        snapshot_date: d.toISOString().slice(0, 10),
        regime: MOOD_HISTORY_CYCLE[i % MOOD_HISTORY_CYCLE.length],
      };
    });
    return HttpResponse.json(items);
  }),

  // GET /api/v1/market/why-today (anonymous)
  http.get('/api/v1/market/why-today', () => {
    return HttpResponse.json({
      snapshot_date: MOOD_SNAPSHOT.snapshot_date,
      regime: MOOD_SNAPSHOT.regime,
      commentary: MOOD_SNAPSHOT.commentary,
      contributing_factors: MOOD_SNAPSHOT.contributing_factors,
      contradicting_factors: MOOD_SNAPSHOT.contradicting_factors,
      disclosure: MOOD_SNAPSHOT.disclosure,
      not_advice: MOOD_SNAPSHOT.not_advice,
      disclaimer_version: MOOD_SNAPSHOT.disclaimer_version,
    });
  }),
];
