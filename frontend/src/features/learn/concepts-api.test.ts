/**
 * learn/concepts — concepts-api.ts unit tests (C1).
 *
 * Tests that:
 *  1. The ConceptListResponse / ConceptDetail shapes parse correctly.
 *  2. The not_advice field (compliance non-negotiable #9) is present and
 *     non-empty on every response shape.
 *  3. fetchConcept returns null on 404 (so pages can call notFound()).
 *  4. fetchConcepts throws on non-OK status.
 *
 * MSW is wired in the global setup (src/test/setup.ts); handlers are added
 * per-test via server.use so this file has no side-effects on the shared
 * handlers. No rendering — server-component rendering requires a Node RSC
 * runtime that vitest/jsdom does not provide (same approach as api.test.ts).
 */
import { http, HttpResponse } from 'msw';
import { server } from '@/mocks/server';
import {
  fetchConcepts,
  fetchConcept,
  type ConceptListResponse,
  type ConceptDetail,
} from './concepts-api';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------
const CONCEPT_SUMMARY = {
  slug: 'compounding',
  title: 'Compounding: growth on growth',
  summary: 'Compounding is earning returns on past returns.',
  category: 'Investing habits',
};

const LIST_RESPONSE: ConceptListResponse = {
  concepts: [CONCEPT_SUMMARY],
  disclosure: 'General investing education — educational content only.',
  not_advice: 'Not investment advice.',
  disclaimer_version: '2026-06-01',
};

const CONCEPT_DETAIL: ConceptDetail = {
  ...CONCEPT_SUMMARY,
  body_md: '## The idea\n\nCompounding is growth earned on growth.',
  updated_at: '2026-06-11T00:00:00+00:00',
  disclosure: 'General investing education — educational content only.',
  not_advice: 'Not investment advice.',
  disclaimer_version: '2026-06-01',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('fetchConcepts', () => {
  it('parses the list response and carries a non-empty not_advice (non-neg #9)', async () => {
    server.use(
      http.get('*/learn/concepts', () => HttpResponse.json(LIST_RESPONSE)),
    );

    const data = await fetchConcepts();
    expect(data.concepts).toHaveLength(1);
    expect(data.concepts[0].slug).toBe('compounding');
    expect(data.not_advice).toBeTruthy();
    expect(data.disclosure).toBeTruthy();
    expect(data.disclaimer_version).toBeTruthy();
  });

  it('passes the category filter as a query param', async () => {
    let seenCategory: string | null = null;
    server.use(
      http.get('*/learn/concepts', ({ request }) => {
        seenCategory = new URL(request.url).searchParams.get('category');
        return HttpResponse.json({ ...LIST_RESPONSE, concepts: [] });
      }),
    );

    const data = await fetchConcepts({ category: 'Risk & return' });
    expect(seenCategory).toBe('Risk & return');
    expect(data.concepts).toEqual([]);
  });

  it('throws on a non-OK status', async () => {
    server.use(
      http.get('*/learn/concepts', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    );

    await expect(fetchConcepts()).rejects.toThrow(/fetchConcepts: 500/);
  });
});

describe('fetchConcept', () => {
  it('parses a concept detail with the disclosure bundle present', async () => {
    server.use(
      http.get('*/learn/concepts/:slug', () => HttpResponse.json(CONCEPT_DETAIL)),
    );

    const concept = await fetchConcept('compounding');
    expect(concept).not.toBeNull();
    expect(concept!.body_md).toContain('## The idea');
    expect(concept!.not_advice).toBeTruthy();
    expect(concept!.disclaimer_version).toBeTruthy();
  });

  it('returns null on 404 so pages can call notFound()', async () => {
    server.use(
      http.get('*/learn/concepts/:slug', () =>
        HttpResponse.json({ detail: 'concept_not_found' }, { status: 404 }),
      ),
    );

    const concept = await fetchConcept('no-such-concept');
    expect(concept).toBeNull();
  });
});
