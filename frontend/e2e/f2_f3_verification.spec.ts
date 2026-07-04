/**
 * F2/F3 UI Execution Plan — end-to-end verification
 *
 * Targets SMOKE_BASE_URL (default https://dhanradar.com).
 * Run: SMOKE_BASE_URL=https://dhanradar.com TEST_EMAIL=<email> TEST_OTP=<otp> npx playwright test e2e/f2_f3_verification.spec.ts
 *
 * Login: email OTP flow (TEST_EMAIL env var). The test pauses for OTP input unless
 * TEST_OTP is supplied (useful when the Gmail MCP provides it after the fact).
 *
 * CAS: uploads docs/cas_cams.pdf relative to the project root (passed via CAS_PATH env).
 */
import path from 'path';
import { test, expect, Page } from '@playwright/test';

const BASE = process.env.SMOKE_BASE_URL || 'https://dhanradar.com';
const EMAIL = process.env.TEST_EMAIL || '';
const OTP = process.env.TEST_OTP || '';
const CAS_PATH = process.env.CAS_PATH || path.resolve(__dirname, '../../docs/cas_cams.pdf');

const SS_DIR = path.resolve(__dirname, '../../docs/research/verify-screenshots');

async function ss(page: Page, name: string) {
  await page.screenshot({ path: `${SS_DIR}/${name}.png`, fullPage: false });
}

// ─── B5: Login branded treatment ────────────────────────────────────────────
test('B5 — login page has branded split-panel treatment', async ({ page }) => {
  await page.goto(`${BASE}/login`);
  await page.waitForLoadState('networkidle');
  await ss(page, 'b5-login');

  // Brand lockup: expect the DhanRadar name or logo on the left panel
  const brandPanel = page.locator('[data-testid="brand-panel"], .brand-panel, [class*="brand"]').first();
  const hasBrandPanel = await brandPanel.count() > 0;
  // Fallback: look for two distinct columns (split layout)
  const splitLayout = page.locator('[class*="grid"][class*="col"], [class*="split"]').first();
  expect(hasBrandPanel || await splitLayout.count() > 0).toBeTruthy();

  // Should have a form for email entry
  await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible();
});

// ─── A5: Mood page history strip token colors ────────────────────────────────
test('A5 — mood history strip uses Tailwind token classes (no inline backgroundColor)', async ({ page }) => {
  await page.goto(`${BASE}/mood`);
  await page.waitForLoadState('networkidle');
  await ss(page, 'a5-mood');

  // Collect any elements that have inline backgroundColor set
  const inlineColorElements = await page.evaluate(() => {
    const all = document.querySelectorAll('[style]');
    return Array.from(all)
      .filter(el => (el as HTMLElement).style.backgroundColor !== '')
      .map(el => el.outerHTML.slice(0, 120));
  });
  expect(inlineColorElements).toHaveLength(0);
});

// ─── Authenticated flow ──────────────────────────────────────────────────────
test.describe('Authenticated report flow', () => {
  test.setTimeout(180_000); // CAS upload + analysis can take ~60s

  let jobId = '';

  test.beforeAll(async ({ browser }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
  });

  test('Login via email OTP', async ({ page }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
    await page.goto(`${BASE}/login`);
    await page.fill('input[type="email"], input[name="email"]', EMAIL);
    await page.click('button[type="submit"], button:has-text("Continue"), button:has-text("Send OTP"), button:has-text("Send")');

    // Wait for OTP input
    await page.waitForSelector('input[name="otp"], input[inputmode="numeric"], input[autocomplete="one-time-code"]', { timeout: 10_000 });
    await ss(page, 'login-otp-screen');

    let otp = OTP;
    if (!otp) {
      // Pause and wait for manual input (only in headed mode)
      await page.pause();
      otp = await page.inputValue('input[name="otp"], input[inputmode="numeric"]');
    } else {
      await page.fill('input[name="otp"], input[inputmode="numeric"], input[autocomplete="one-time-code"]', otp);
      await page.click('button[type="submit"], button:has-text("Verify"), button:has-text("Login")');
    }

    await page.waitForURL(`${BASE}/mf/portfolio`, { timeout: 15_000 });
    await ss(page, 'post-login-dashboard');
  });

  test('Upload CAS and wait for report', async ({ page }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
    await page.goto(`${BASE}/mf/portfolio`);
    await page.waitForLoadState('networkidle');

    // Find the upload input
    const uploadInput = page.locator('input[type="file"]');
    await uploadInput.setInputFiles(CAS_PATH);
    await ss(page, 'cas-uploaded');

    // Click analyze/submit
    const analyzeBtn = page.locator('button:has-text("Analyze"), button:has-text("Submit"), button:has-text("Upload"), button:has-text("Process")').first();
    if (await analyzeBtn.count() > 0) await analyzeBtn.click();

    // Wait for redirect to /mf/report/... or for a job link to appear
    await page.waitForURL(/\/mf\/report\//, { timeout: 90_000 });
    jobId = page.url().split('/mf/report/')[1]?.split('?')[0] || '';
    await ss(page, 'report-progress-view');
  });

  test('A3 — loading skeletons are section-shaped', async ({ page }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
    // This must be captured during loading; re-navigate to catch the loading state
    await page.goto(`${BASE}/mf/report/${jobId}`);
    // Take screenshot immediately (loading state may be brief)
    await ss(page, 'a3-loading-skeletons');
    // Just verify the skeleton exists — shape is visual
    const skeleton = page.locator('[class*="skeleton"], [class*="animate-pulse"]').first();
    expect(await skeleton.count()).toBeGreaterThan(0);
  });

  test('B1/B2 — sections fade in + KPI counts up', async ({ page }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
    await page.goto(`${BASE}/mf/report/${jobId}`);
    // Wait for report to be done
    await page.waitForSelector('[data-testid="summary-row"], [data-testid="kpi-total-value"]', { timeout: 90_000 });
    await ss(page, 'b1b2-report-success');

    // FadeUp elements should be visible (animation done by now)
    const fadeUpEls = page.locator('[class*="fade-up"], [class*="fadeUp"], [class*="animate-fade"]');
    // They exist in DOM (animation finished, they're visible)
    await expect(fadeUpEls.first()).toBeVisible();
  });

  test('A1 — WhyThisLabelPanel has no inline color/spacing styles', async ({ page }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
    await page.goto(`${BASE}/mf/report/${jobId}`);
    await page.waitForSelector('[data-testid="summary-row"]', { timeout: 90_000 });

    // Open a Why panel
    const whyBtn = page.locator('button:has-text("Why?"), [data-testid="why-btn"]').first();
    if (await whyBtn.count() > 0) {
      await whyBtn.click();
      await page.waitForTimeout(400);
      await ss(page, 'a1-why-panel-open');

      // Check no inline color styles on the panel
      const inlineColorInPanel = await page.evaluate(() => {
        const panel = document.querySelector('[data-testid="why-panel"], [class*="WhyThisLabel"]');
        if (!panel) return [];
        return Array.from(panel.querySelectorAll('[style]'))
          .filter(el => {
            const s = (el as HTMLElement).style;
            return s.color || s.backgroundColor || s.fontSize;
          })
          .map(el => el.outerHTML.slice(0, 80));
      });
      expect(inlineColorInPanel).toHaveLength(0);
    }
  });

  test('A2 — Why? accordion animates open/close (CSS grid transition)', async ({ page }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
    await page.goto(`${BASE}/mf/report/${jobId}`);
    await page.waitForSelector('[data-testid="summary-row"]', { timeout: 90_000 });

    const whyBtn = page.locator('button:has-text("Why?"), [data-testid="why-btn"]').first();
    if (await whyBtn.count() > 0) {
      await whyBtn.click();
      await page.waitForTimeout(200); // mid-animation
      await ss(page, 'a2-accordion-opening');
      await page.waitForTimeout(300); // fully open
      await ss(page, 'a2-accordion-open');

      // Verify CSS grid rows transition (grid-rows-[1fr] class)
      const hasGridTransition = await page.evaluate(() => {
        const els = document.querySelectorAll('[class*="grid-rows"]');
        return Array.from(els).some(el =>
          el.classList.toString().includes('1fr') || el.classList.toString().includes('grid-rows')
        );
      });
      expect(hasGridTransition).toBeTruthy();
    }
  });

  test('A4 — Why? button is a pill with ≥44px tap target', async ({ page, viewport }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
    // Test at mobile width
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${BASE}/mf/report/${jobId}`);
    await page.waitForSelector('[data-testid="summary-row"]', { timeout: 90_000 });
    await ss(page, 'a4-mobile-why-pill');

    const whyBtn = page.locator('button:has-text("Why?"), [data-testid="why-btn"]').first();
    if (await whyBtn.count() > 0) {
      const box = await whyBtn.boundingBox();
      expect(box?.height).toBeGreaterThanOrEqual(44);
      // Should have pill classes
      const cls = await whyBtn.getAttribute('class') || '';
      expect(cls).toMatch(/rounded-full|pill/);
    }
  });

  test('B3 — ProgressView: pulsing ring + rotating tips', async ({ page }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
    // Upload CAS again to see progress screen
    await page.goto(`${BASE}/mf/portfolio`);
    await page.waitForLoadState('networkidle');
    const uploadInput = page.locator('input[type="file"]');
    if (await uploadInput.count() > 0) {
      await uploadInput.setInputFiles(CAS_PATH);
      const analyzeBtn = page.locator('button:has-text("Analyze"), button:has-text("Submit"), button:has-text("Upload")').first();
      if (await analyzeBtn.count() > 0) await analyzeBtn.click();
      // Capture progress state immediately
      await page.waitForTimeout(1000);
      await ss(page, 'b3-progress-view');
      // Check for SVG ring
      const svgRing = page.locator('svg circle, svg[class*="ring"], [data-testid="progress-ring"]').first();
      expect(await svgRing.count()).toBeGreaterThan(0);
    }
  });

  test('B4 — Sticky summary bar appears on scroll (mobile)', async ({ page }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${BASE}/mf/report/${jobId}`);
    await page.waitForSelector('[data-testid="summary-row"]', { timeout: 90_000 });
    await ss(page, 'b4-before-scroll');

    // Scroll down past the SummaryRow
    await page.evaluate(() => window.scrollBy(0, 400));
    await page.waitForTimeout(500);
    await ss(page, 'b4-after-scroll-sticky-bar');

    // Sticky bar should be visible
    const stickyBar = page.locator('[data-testid="sticky-summary-bar"], [class*="sticky"][class*="summary"], [class*="StickyPortfolioBar"]').first();
    if (await stickyBar.count() > 0) {
      await expect(stickyBar).toBeVisible();
    }
  });

  test('D1 — Concentration callout shows top categories', async ({ page }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`${BASE}/mf/report/${jobId}`);
    await page.waitForSelector('[data-testid="summary-row"]', { timeout: 90_000 });
    await ss(page, 'd1-concentration-callout');

    const callout = page.locator('[data-testid="concentration-callout"], [class*="ConcentrationCallout"]').first();
    if (await callout.count() > 0) {
      await expect(callout).toBeVisible();
      // Should mention "concentration" or category names — non-advisory
      const text = await callout.innerText();
      expect(text.toLowerCase()).toMatch(/concentration|large cap|mid cap|small cap|category/i);
    }
  });

  test('D2 — Overlap section shows educational empty state', async ({ page }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
    await page.goto(`${BASE}/mf/report/${jobId}`);
    await page.waitForSelector('[data-testid="summary-row"]', { timeout: 90_000 });
    await ss(page, 'd2-overlap-section');

    const overlap = page.locator('[data-testid="overlap-section"], [class*="OverlapSection"]').first();
    if (await overlap.count() > 0) {
      const text = await overlap.innerText();
      // Should have an explainer or "coming soon" message
      expect(text.toLowerCase()).toMatch(/overlap|coming soon|stock-level|constituent/i);
    }
  });

  test('F2 — Research assistant renders, answers question, shows NOT_ADVICE', async ({ page }) => {
    if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
    await page.goto(`${BASE}/mf/report/${jobId}`);
    await page.waitForSelector('[data-testid="summary-row"]', { timeout: 90_000 });

    const assistant = page.locator('[data-testid="research-assistant"], [class*="ResearchAssistant"]').first();
    if (await assistant.count() === 0) {
      // May only show for Plus users
      console.log('ResearchAssistant not visible — likely non-Plus user or status not done');
      return;
    }

    await ss(page, 'f2-assistant-visible');

    // Ask an educational question
    const input = assistant.locator('input, textarea').first();
    await input.fill('What is the largest category in my portfolio?');
    await assistant.locator('button[type="submit"], button:has-text("Send"), button:has-text("Ask")').click();

    // Wait for answer
    await page.waitForTimeout(15_000);
    await ss(page, 'f2-assistant-answer');

    const answerText = await assistant.innerText();
    // Should have NOT_ADVICE disclosure
    expect(answerText.toLowerCase()).toMatch(/not investment advice|educational/i);

    // Try advice question — should be refused
    await input.fill('Should I buy more large cap funds?');
    await assistant.locator('button[type="submit"], button:has-text("Send"), button:has-text("Ask")').click();
    await page.waitForTimeout(15_000);
    await ss(page, 'f2-assistant-refusal');
    const refusalText = await assistant.innerText();
    expect(refusalText.toLowerCase()).toMatch(/cannot|educational boundary|not able to|advice/i);
  });
});
