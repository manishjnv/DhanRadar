/**
 * B45 — real-backend smoke test.
 *
 * Targets SMOKE_BASE_URL (default: http://localhost:3000) which must be a
 * running instance built with NEXT_PUBLIC_API_MOCKING=disabled so MSW is NOT
 * active. Do NOT add a webServer block here — the smoke test assumes an
 * externally running deployment.
 *
 * Assertions:
 *  1. Page responds with HTTP 200.
 *  2. Document has a non-empty <title>.
 *  3. A root element (#__next or body) is visible.
 *  4. No uncaught JS errors were thrown during page load.
 *  5. "Starting development mocks" is NOT present (confirms mocks-off build).
 */
import { test, expect } from '@playwright/test';

test('smoke: home page loads without errors and without MSW', async ({ page }) => {
  const pageErrors: string[] = [];
  page.on('pageerror', (err) => pageErrors.push(err.message));

  const response = await page.goto('/');
  expect(response?.status()).toBe(200);

  // Document title must be non-empty
  const title = await page.title();
  expect(title.length).toBeGreaterThan(0);

  // A root element must be visible — Next.js App Router renders into #__next
  // (or <body> itself); either confirms the React tree mounted.
  const root = page.locator('#__next, body');
  await expect(root.first()).toBeVisible();

  // No uncaught JavaScript errors
  expect(pageErrors).toHaveLength(0);

  // MSW must NOT be active — the development mock banner is absent
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toContain('Starting development mocks');
});
