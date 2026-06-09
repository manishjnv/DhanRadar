/**
 * learn/tax — api.ts unit tests.
 *
 * Tests that:
 *  1. The response shapes for TaxArticleListResponse / TaxArticleDetail /
 *     TaxCalendar parse correctly (all required fields present, correct types).
 *  2. The not_advice field (compliance non-negotiable #9) is present and
 *     non-empty on every response shape.
 *  3. fetchTaxArticle returns null on 404 (so pages can call notFound()).
 *  4. fetchTaxArticles / fetchTaxCalendar throw on non-OK status.
 *
 * MSW is wired in the global setup (src/test/setup.ts) but we manage a local
 * override server here so this file has no side-effects on the shared handlers.
 *
 * We keep the test env lightweight: no rendering, no DOM, pure fetch + type
 * assertions. Server-component rendering requires a Node RSC runtime that
 * vitest/jsdom does not provide.
 */

import { http, HttpResponse } from 'msw';
import { server } from '@/mocks/server';
import {
  fetchTaxArticles,
  fetchTaxArticle,
  fetchTaxCalendar,
  type TaxArticleListResponse,
  type TaxArticleDetail,
  type TaxCalendar,
} from './api';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------
const ARTICLE_SUMMARY = {
  slug:     'capital-gains-explainer',
  title:    'Capital Gains: Short-term vs Long-term',
  summary:  'Understand how STCG and LTCG are taxed in India.',
  category: 'Capital Gains',
  fy_label: 'FY 2025-26',
};

const LIST_RESPONSE: TaxArticleListResponse = {
  articles:           [ARTICLE_SUMMARY],
  disclosure:         'Educational content based on publicly available SEBI and IT circulars.',
  not_advice:         'This is not investment or tax advice.',
  disclaimer_version: '2026-06-01',
};

const ARTICLE_DETAIL: TaxArticleDetail = {
  ...ARTICLE_SUMMARY,
  body_md:            '## What are Capital Gains?\n\nCapital gains are profits from the sale of assets.',
  source_note:        'Based on Income Tax Act 1961, Section 45.',
  updated_at:         '2026-06-01',
  disclosure:         'Educational content — refer to a qualified CA for personal advice.',
  not_advice:         'This is not investment or tax advice.',
  disclaimer_version: '2026-06-01',
};

const CALENDAR_RESPONSE: TaxCalendar = {
  fy_label:  'FY 2025-26',
  fy_start:  '2025-04-01',
  fy_end:    '2026-03-31',
  key_dates: [
    { label: 'Advance Tax Q1', date: '2025-06-15', note: 'Pay 15% of estimated tax.' },
    { label: 'ITR filing deadline', date: '2026-07-31', note: 'Non-audit cases.' },
  ],
  elss_note:          'ELSS investments made before 31 March qualify for Section 80C deduction.',
  disclosure:         'Educational content — refer to a qualified CA for personal advice.',
  not_advice:         'This is not investment or tax advice.',
  disclaimer_version: '2026-06-01',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function addHandlers() {
  server.use(
    http.get('*/learn/tax/calendar', () =>
      HttpResponse.json(CALENDAR_RESPONSE),
    ),
    http.get('*/learn/tax/capital-gains-explainer', () =>
      HttpResponse.json(ARTICLE_DETAIL),
    ),
    http.get('*/learn/tax/unknown-slug', () =>
      HttpResponse.json(
        { type: 'about:blank', title: 'Not Found', status: 404, request_id: 'mock-404' },
        { status: 404 },
      ),
    ),
    http.get('*/learn/tax/error-slug', () =>
      HttpResponse.json(
        { type: 'about:blank', title: 'Internal Server Error', status: 500, request_id: 'mock-500' },
        { status: 500 },
      ),
    ),
    http.get('*/learn/tax', () =>
      HttpResponse.json(LIST_RESPONSE),
    ),
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('fetchTaxArticles', () => {
  beforeEach(() => addHandlers());

  it('returns a list with articles and disclosure fields', async () => {
    const result = await fetchTaxArticles();

    expect(result.articles).toHaveLength(1);
    expect(result.articles[0].slug).toBe('capital-gains-explainer');
    expect(result.articles[0].title).toBeTruthy();
    expect(result.articles[0].summary).toBeTruthy();
    expect(result.articles[0].category).toBeTruthy();
    expect(result.articles[0].fy_label).toBeTruthy();
  });

  it('includes non-empty not_advice (compliance #9)', async () => {
    const result = await fetchTaxArticles();

    expect(result.not_advice).toBeTruthy();
    expect(typeof result.not_advice).toBe('string');
    expect(result.not_advice.length).toBeGreaterThan(0);
  });

  it('includes disclosure string (compliance #9)', async () => {
    const result = await fetchTaxArticles();

    expect(result.disclosure).toBeTruthy();
    expect(typeof result.disclosure).toBe('string');
  });

  it('includes disclaimer_version', async () => {
    const result = await fetchTaxArticles();

    expect(result.disclaimer_version).toBeTruthy();
  });

  it('throws on non-OK status', async () => {
    server.use(
      http.get('*/learn/tax', () =>
        HttpResponse.json({}, { status: 503 }),
      ),
    );
    await expect(fetchTaxArticles()).rejects.toThrow();
  });
});

describe('fetchTaxArticle', () => {
  beforeEach(() => addHandlers());

  it('returns article detail with all required fields', async () => {
    const result = await fetchTaxArticle('capital-gains-explainer');

    expect(result).not.toBeNull();
    expect(result!.slug).toBe('capital-gains-explainer');
    expect(result!.title).toBeTruthy();
    expect(result!.summary).toBeTruthy();
    expect(result!.body_md).toBeTruthy();
    expect(result!.source_note).toBeTruthy();
    expect(result!.updated_at).toBeTruthy();
    expect(result!.category).toBeTruthy();
    expect(result!.fy_label).toBeTruthy();
  });

  it('includes non-empty not_advice on article detail (compliance #9)', async () => {
    const result = await fetchTaxArticle('capital-gains-explainer');

    expect(result).not.toBeNull();
    expect(result!.not_advice).toBeTruthy();
    expect(typeof result!.not_advice).toBe('string');
    expect(result!.not_advice.length).toBeGreaterThan(0);
  });

  it('includes disclosure on article detail (compliance #9)', async () => {
    const result = await fetchTaxArticle('capital-gains-explainer');

    expect(result).not.toBeNull();
    expect(result!.disclosure).toBeTruthy();
  });

  it('returns null on 404 so pages can call notFound()', async () => {
    const result = await fetchTaxArticle('unknown-slug');

    expect(result).toBeNull();
  });

  it('throws on non-404 error status', async () => {
    await expect(fetchTaxArticle('error-slug')).rejects.toThrow();
  });
});

describe('fetchTaxCalendar', () => {
  beforeEach(() => addHandlers());

  it('returns calendar with fy_label, fy_start, fy_end', async () => {
    const result = await fetchTaxCalendar();

    expect(result.fy_label).toBeTruthy();
    expect(result.fy_start).toBeTruthy();
    expect(result.fy_end).toBeTruthy();
  });

  it('returns an array of key_dates with required fields', async () => {
    const result = await fetchTaxCalendar();

    expect(Array.isArray(result.key_dates)).toBe(true);
    expect(result.key_dates.length).toBeGreaterThan(0);

    for (const entry of result.key_dates) {
      expect(entry.label).toBeTruthy();
      expect(entry.date).toBeTruthy();
      // note is optional but should be a string when present
      if (entry.note !== undefined) {
        expect(typeof entry.note).toBe('string');
      }
    }
  });

  it('includes non-empty not_advice (compliance #9)', async () => {
    const result = await fetchTaxCalendar();

    expect(result.not_advice).toBeTruthy();
    expect(typeof result.not_advice).toBe('string');
    expect(result.not_advice.length).toBeGreaterThan(0);
  });

  it('includes disclosure string (compliance #9)', async () => {
    const result = await fetchTaxCalendar();

    expect(result.disclosure).toBeTruthy();
  });

  it('includes elss_note', async () => {
    const result = await fetchTaxCalendar();

    expect(typeof result.elss_note).toBe('string');
  });

  it('throws on non-OK status', async () => {
    server.use(
      http.get('*/learn/tax/calendar', () =>
        HttpResponse.json({}, { status: 503 }),
      ),
    );
    await expect(fetchTaxCalendar()).rejects.toThrow();
  });
});
