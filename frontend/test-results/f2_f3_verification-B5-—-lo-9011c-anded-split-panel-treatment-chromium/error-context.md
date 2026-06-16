# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: f2_f3_verification.spec.ts >> B5 — login page has branded split-panel treatment
- Location: e2e\f2_f3_verification.spec.ts:27:5

# Error details

```
Error: expect(received).toBeTruthy()

Received: false
```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e2]:
    - generic [ref=e3]:
      - generic [ref=e4]:
        - paragraph [ref=e5]: DhanRadar
        - paragraph [ref=e6]: Educational market intelligence
      - generic [ref=e7]:
        - paragraph [ref=e8]: Understand your mutual fund portfolio in 60 seconds.
        - paragraph [ref=e9]: Upload your CAS statement for an educational label analysis of your holdings — no buy, sell, or hold recommendations, ever.
      - paragraph [ref=e10]: Not investment advice.
    - main [ref=e11]:
      - generic [ref=e13]:
        - heading "Log in" [level=3] [ref=e15]
        - generic [ref=e16]:
          - generic [ref=e17]:
            - generic [ref=e18]:
              - generic [ref=e19]: Email
              - textbox "Email" [ref=e20]:
                - /placeholder: you@example.com
            - generic [ref=e21]:
              - generic [ref=e22]: Password
              - textbox "Password" [ref=e23]
            - button "Log in" [ref=e24] [cursor=pointer]
            - button "Sign in with email code" [ref=e25] [cursor=pointer]
          - generic [ref=e30]: or
          - button "Continue with Google" [ref=e31] [cursor=pointer]
          - paragraph [ref=e32]:
            - text: New to DhanRadar?
            - link "Create an account" [ref=e33] [cursor=pointer]:
              - /url: /signup
      - note [ref=e34]: Educational information, not investment advice. DhanRadar is a research analytics product. SEBI registration does not guarantee accuracy.
  - region "Notifications alt+T"
  - alert [ref=e35]
```

# Test source

```ts
  1   | /**
  2   |  * F2/F3 UI Execution Plan — end-to-end verification
  3   |  *
  4   |  * Targets SMOKE_BASE_URL (default https://dhanradar.com).
  5   |  * Run: SMOKE_BASE_URL=https://dhanradar.com TEST_EMAIL=<email> TEST_OTP=<otp> npx playwright test e2e/f2_f3_verification.spec.ts
  6   |  *
  7   |  * Login: email OTP flow (TEST_EMAIL env var). The test pauses for OTP input unless
  8   |  * TEST_OTP is supplied (useful when the Gmail MCP provides it after the fact).
  9   |  *
  10  |  * CAS: uploads docs/cas_cams.pdf relative to the project root (passed via CAS_PATH env).
  11  |  */
  12  | import path from 'path';
  13  | import { test, expect, Page } from '@playwright/test';
  14  | 
  15  | const BASE = process.env.SMOKE_BASE_URL || 'https://dhanradar.com';
  16  | const EMAIL = process.env.TEST_EMAIL || '';
  17  | const OTP = process.env.TEST_OTP || '';
  18  | const CAS_PATH = process.env.CAS_PATH || path.resolve(__dirname, '../../docs/cas_cams.pdf');
  19  | 
  20  | const SS_DIR = path.resolve(__dirname, '../../docs/research/verify-screenshots');
  21  | 
  22  | async function ss(page: Page, name: string) {
  23  |   await page.screenshot({ path: `${SS_DIR}/${name}.png`, fullPage: false });
  24  | }
  25  | 
  26  | // ─── B5: Login branded treatment ────────────────────────────────────────────
  27  | test('B5 — login page has branded split-panel treatment', async ({ page }) => {
  28  |   await page.goto(`${BASE}/login`);
  29  |   await page.waitForLoadState('networkidle');
  30  |   await ss(page, 'b5-login');
  31  | 
  32  |   // Brand lockup: expect the DhanRadar name or logo on the left panel
  33  |   const brandPanel = page.locator('[data-testid="brand-panel"], .brand-panel, [class*="brand"]').first();
  34  |   const hasBrandPanel = await brandPanel.count() > 0;
  35  |   // Fallback: look for two distinct columns (split layout)
  36  |   const splitLayout = page.locator('[class*="grid"][class*="col"], [class*="split"]').first();
> 37  |   expect(hasBrandPanel || await splitLayout.count() > 0).toBeTruthy();
      |                                                          ^ Error: expect(received).toBeTruthy()
  38  | 
  39  |   // Should have a form for email entry
  40  |   await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible();
  41  | });
  42  | 
  43  | // ─── A5: Mood page history strip token colors ────────────────────────────────
  44  | test('A5 — mood history strip uses Tailwind token classes (no inline backgroundColor)', async ({ page }) => {
  45  |   await page.goto(`${BASE}/mood`);
  46  |   await page.waitForLoadState('networkidle');
  47  |   await ss(page, 'a5-mood');
  48  | 
  49  |   // Collect any elements that have inline backgroundColor set
  50  |   const inlineColorElements = await page.evaluate(() => {
  51  |     const all = document.querySelectorAll('[style]');
  52  |     return Array.from(all)
  53  |       .filter(el => (el as HTMLElement).style.backgroundColor !== '')
  54  |       .map(el => el.outerHTML.slice(0, 120));
  55  |   });
  56  |   expect(inlineColorElements).toHaveLength(0);
  57  | });
  58  | 
  59  | // ─── Authenticated flow ──────────────────────────────────────────────────────
  60  | test.describe('Authenticated report flow', () => {
  61  |   test.setTimeout(180_000); // CAS upload + analysis can take ~60s
  62  | 
  63  |   let jobId = '';
  64  | 
  65  |   test.beforeAll(async ({ browser }) => {
  66  |     if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
  67  |   });
  68  | 
  69  |   test('Login via email OTP', async ({ page }) => {
  70  |     if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
  71  |     await page.goto(`${BASE}/login`);
  72  |     await page.fill('input[type="email"], input[name="email"]', EMAIL);
  73  |     await page.click('button[type="submit"], button:has-text("Continue"), button:has-text("Send OTP"), button:has-text("Send")');
  74  | 
  75  |     // Wait for OTP input
  76  |     await page.waitForSelector('input[name="otp"], input[inputmode="numeric"], input[autocomplete="one-time-code"]', { timeout: 10_000 });
  77  |     await ss(page, 'login-otp-screen');
  78  | 
  79  |     let otp = OTP;
  80  |     if (!otp) {
  81  |       // Pause and wait for manual input (only in headed mode)
  82  |       await page.pause();
  83  |       otp = await page.inputValue('input[name="otp"], input[inputmode="numeric"]');
  84  |     } else {
  85  |       await page.fill('input[name="otp"], input[inputmode="numeric"], input[autocomplete="one-time-code"]', otp);
  86  |       await page.click('button[type="submit"], button:has-text("Verify"), button:has-text("Login")');
  87  |     }
  88  | 
  89  |     await page.waitForURL(`${BASE}/dashboard`, { timeout: 15_000 });
  90  |     await ss(page, 'post-login-dashboard');
  91  |   });
  92  | 
  93  |   test('Upload CAS and wait for report', async ({ page }) => {
  94  |     if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
  95  |     await page.goto(`${BASE}/dashboard`);
  96  |     await page.waitForLoadState('networkidle');
  97  | 
  98  |     // Find the upload input
  99  |     const uploadInput = page.locator('input[type="file"]');
  100 |     await uploadInput.setInputFiles(CAS_PATH);
  101 |     await ss(page, 'cas-uploaded');
  102 | 
  103 |     // Click analyze/submit
  104 |     const analyzeBtn = page.locator('button:has-text("Analyze"), button:has-text("Submit"), button:has-text("Upload"), button:has-text("Process")').first();
  105 |     if (await analyzeBtn.count() > 0) await analyzeBtn.click();
  106 | 
  107 |     // Wait for redirect to /mf/report/... or for a job link to appear
  108 |     await page.waitForURL(/\/mf\/report\//, { timeout: 90_000 });
  109 |     jobId = page.url().split('/mf/report/')[1]?.split('?')[0] || '';
  110 |     await ss(page, 'report-progress-view');
  111 |   });
  112 | 
  113 |   test('A3 — loading skeletons are section-shaped', async ({ page }) => {
  114 |     if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
  115 |     // This must be captured during loading; re-navigate to catch the loading state
  116 |     await page.goto(`${BASE}/mf/report/${jobId}`);
  117 |     // Take screenshot immediately (loading state may be brief)
  118 |     await ss(page, 'a3-loading-skeletons');
  119 |     // Just verify the skeleton exists — shape is visual
  120 |     const skeleton = page.locator('[class*="skeleton"], [class*="animate-pulse"]').first();
  121 |     expect(await skeleton.count()).toBeGreaterThan(0);
  122 |   });
  123 | 
  124 |   test('B1/B2 — sections fade in + KPI counts up', async ({ page }) => {
  125 |     if (!EMAIL) test.skip(true, 'TEST_EMAIL not set');
  126 |     await page.goto(`${BASE}/mf/report/${jobId}`);
  127 |     // Wait for report to be done
  128 |     await page.waitForSelector('[data-testid="summary-row"], [data-testid="kpi-total-value"]', { timeout: 90_000 });
  129 |     await ss(page, 'b1b2-report-success');
  130 | 
  131 |     // FadeUp elements should be visible (animation done by now)
  132 |     const fadeUpEls = page.locator('[class*="fade-up"], [class*="fadeUp"], [class*="animate-fade"]');
  133 |     // They exist in DOM (animation finished, they're visible)
  134 |     await expect(fadeUpEls.first()).toBeVisible();
  135 |   });
  136 | 
  137 |   test('A1 — WhyThisLabelPanel has no inline color/spacing styles', async ({ page }) => {
```