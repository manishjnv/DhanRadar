// End-to-end invest-wizard run with screenshot capture.
// Auth: __Host-access cookie minted server-side (scratchpad/.acc, re-read after OTP wait).
// OTP: polls scratchpad/otp.txt (written by the operator when the email arrives).
import { chromium } from 'playwright';
import { readFileSync, existsSync, mkdirSync } from 'fs';
import path from 'path';

const SCRATCH = 'C:/Users/manis/AppData/Local/Temp/claude/e--code-DhanRadar/b1e1a8d8-b904-4bd9-8f91-d94661993687/scratchpad';
const OUT = 'e:/code/DhanRadar/docs/Sample/BSE_Star_MF_API/screenshots';
const BASE = 'https://dhanradar.com';
const ISIN = 'INF090I01BG0';
const BSE_PW = 'Member@123'; // documented UAT demo password (bse-api.md)

mkdirSync(OUT, { recursive: true });
const log = (m) => console.log(`[cap] ${m}`);
const token = () => readFileSync(path.join(SCRATCH, '.acc'), 'utf8').trim();

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const addAuth = async () =>
  ctx.addCookies([{ name: '__Host-access', value: token(), domain: 'dhanradar.com', path: '/', secure: true, httpOnly: true, sameSite: 'Lax' }]);
await addAuth();
const page = await ctx.newPage();
const shot = async (name) => { await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false }); log(`shot ${name}`); };

try {
  // ---- fig 1: fund page with CTAs
  await page.goto(`${BASE}/mf/fund/${ISIN}`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(2500);
  await shot('1-fund-page');

  // ---- open wizard
  await page.getByRole('link', { name: /Invest Now/ }).first().click();
  await page.waitForURL(/\/mf\/invest\//, { timeout: 30000 });
  await page.waitForTimeout(1500);

  // ---- BSE session login via the UI session bar
  const pw = page.getByPlaceholder(/BSE member password/i).first();
  if (await pw.isVisible().catch(() => false)) {
    await pw.fill(BSE_PW);
    await page.getByRole('button', { name: /Login to BSE UAT/i }).click();
    await page.waitForTimeout(4000);
    log('BSE session logged in');
  } else {
    log('session bar shows active — skipping login');
  }

  // ---- step 1: lumpsum ₹10,000 (default) → continue
  await page.getByRole('button', { name: /One-time Lumpsum/i }).first().click().catch(() => log('lumpsum toggle default'));
  await page.waitForTimeout(800);
  await page.getByRole('button', { name: /Continue to verification/i }).click();
  await page.waitForTimeout(1000);

  // ---- step 2: load profile → fig 2
  await page.getByRole('button', { name: /Load investor profile/i }).click();
  await page.waitForTimeout(5000);
  await shot('2-verification');
  await page.getByRole('button', { name: /Continue to payment/i }).click();
  await page.waitForTimeout(800);
  await page.getByRole('button', { name: /Continue to review/i }).click();
  await page.waitForTimeout(1200);

  // ---- step 5: consent → fig 3 → confirm
  await page.locator('input[type="checkbox"]').first().check();
  await page.waitForTimeout(400);
  await shot('3-review');
  await page.getByRole('button', { name: /Confirm & place order/i }).click();
  await page.waitForTimeout(6000);
  await shot('4-order-placed');
  const bodyText = await page.textContent('body');
  const om = bodyText.match(/Order\s+(\d{10})/);
  log(`ORDER_ID=${om ? om[1] : 'NOT-FOUND'}`);

  // ---- step 6: send OTP, wait for operator to write otp.txt
  await page.getByRole('button', { name: /Send OTP/i }).click();
  await page.waitForTimeout(5000);
  log('OTP requested — waiting for scratchpad/otp.txt (up to 25 min)');
  const otpFile = 'e:/code/DhanRadar/frontend/otp.txt';
  let otp = null;
  for (let i = 0; i < 300; i++) {
    if (existsSync(otpFile)) {
      const v = readFileSync(otpFile, 'utf8').trim();
      if (/^\d{4,8}$/.test(v)) { otp = v; break; }
    }
    await page.waitForTimeout(5000);
  }
  if (!otp) throw new Error('no OTP provided within 25 min');
  log('OTP received — re-arming auth + submitting');
  await addAuth(); // .acc may have been re-minted during the wait

  await page.locator('input[inputmode="numeric"], input[placeholder*="OTP" i], input[aria-label*="OTP" i]').last().fill(otp);
  await page.getByRole('button', { name: /Approve order/i }).click();
  await page.waitForTimeout(6000);
  await shot('5-approved');

  // ---- fig 6: give webhooks ~75s, timeline polls every 5s
  log('waiting 75s for payment_pending webhook…');
  await page.waitForTimeout(75000);
  await shot('6-timeline');

  log('DONE');
} catch (e) {
  await shot('error-state').catch(() => {});
  log(`FAILED: ${e.message}`);
  process.exitCode = 1;
} finally {
  await browser.close();
}
