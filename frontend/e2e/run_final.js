/**
 * Final verification pass — captures only what the main run missed:
 * B1/B2 (stagger/count-up), A4 (mobile pill), B4 (sticky scroll), F2 answer/refusal.
 * Uses TEST_OTP env var (no file polling — pass the code directly).
 */
const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const SS_DIR = path.resolve(__dirname, '../../docs/research/verify-screenshots');
const JOB_ID = process.env.JOB_ID || 'c8ac86ff-a3bb-4d5a-a21c-e07c1db869ef';
const OTP_FILE = 'C:/Users/manis/AppData/Local/Temp/dhanradar_otp.txt';
const PRE_OTP = process.env.TEST_OTP || '';

if (fs.existsSync(OTP_FILE)) fs.unlinkSync(OTP_FILE);

const REPORT_URL = `https://dhanradar.com/mf/report/${JOB_ID}`;
const REPORT_READY = 'text=Total invested';

(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage();

  // ── LOGIN ────────────────────────────────────────────────────────────────
  await p.goto('https://dhanradar.com/login');
  await p.waitForLoadState('networkidle');
  await p.fill('input[name="email"]', 'manishjnvk@gmail.com');
  await p.click('button:has-text("Sign in with email code")');
  await p.waitForTimeout(500);
  await p.click('button:has-text("Email me a login code")');
  console.log('OTP_SENT');
  await p.waitForSelector('input[id="code"]', { timeout: 15000 });

  let otp = PRE_OTP;
  if (!otp) {
    for (let i = 0; i < 90; i++) {
      if (fs.existsSync(OTP_FILE)) {
        otp = fs.readFileSync(OTP_FILE, 'utf8').trim();
        if (/^\d{6}$/.test(otp)) break;
        otp = '';
      }
      await new Promise(r => setTimeout(r, 1000));
    }
  }
  if (!otp) { console.error('OTP_TIMEOUT'); await b.close(); process.exit(1); }
  console.log('OTP_USING:' + otp);

  await p.fill('input[id="code"]', otp);
  await p.locator('button[type="submit"]').first().click();
  await p.waitForURL(url => !url.toString().includes('/login'), { timeout: 15000 });
  console.log('LOGGED_IN');

  // ── B1/B2: Fresh navigate + early screenshot ─────────────────────────────
  await p.setViewportSize({ width: 1280, height: 800 });
  await p.goto(REPORT_URL);
  await p.waitForTimeout(200);
  await p.screenshot({ path: SS_DIR + '/b1b2-early.png' });
  const earlyFade = await p.locator('[class*="animate-pulse"]').count();
  console.log('B1B2_EARLY_ANIMATE_COUNT:' + earlyFade);
  // Wait for report loaded
  await p.waitForSelector(REPORT_READY, { timeout: 30000 });
  await p.screenshot({ path: SS_DIR + '/b1b2-loaded.png' });
  // FadeUp elements — the FadeUp wrapper adds opacity+transform via JS; check class in DOM
  const fadeWrappers = await p.evaluate(() =>
    Array.from(document.querySelectorAll('*')).filter(el => {
      const cl = el.className?.toString?.() || '';
      return cl.includes('animate-fade') || cl.includes('fade-up') || cl.includes('FadeUp');
    }).length
  );
  console.log('B1B2_FADEUP_WRAPPERS:' + fadeWrappers);
  // Count-up: the KPI values contain decimal points (e.g. ₹1,47,425.66) — verify
  const kpiText = await p.locator('text=TOTAL INVESTED').first().evaluate(el => el.parentElement?.textContent || '');
  console.log('B2_KPI_TEXT:' + kpiText.replace(/\n/g, ' ').slice(0, 80));

  // ── F2: Research assistant — wait properly for response ──────────────────
  await p.goto(REPORT_URL);
  await p.waitForSelector(REPORT_READY, { timeout: 30000 });
  // Scroll to bottom to see the assistant
  await p.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await p.waitForTimeout(400);
  const assistantTitle = p.locator('text=Portfolio Research Assistant').first();
  if (await assistantTitle.count() > 0) {
    await p.screenshot({ path: SS_DIR + '/f2-visible.png' });
    const form = p.locator('form').first();
    const qInput = form.locator('input, textarea').first();

    // Ask educational question
    await qInput.waitFor({ state: 'visible', timeout: 10000 });
    // Wait for textarea to be enabled (not disabled)
    await p.waitForSelector('textarea:not([disabled])', { timeout: 30000 });
    await qInput.fill('What is the largest category in my portfolio?');
    const sendBtn = form.locator('button[type="submit"]').first();
    await sendBtn.click();
    console.log('F2_Q1_SENT');
    await p.screenshot({ path: SS_DIR + '/f2-asking.png' });

    // Wait for the textarea to become enabled again (answer received)
    try {
      await p.waitForSelector('textarea:not([disabled])', { timeout: 90000 });
      await p.screenshot({ path: SS_DIR + '/f2-answered.png' });
      const cardText = await assistantTitle.evaluate(el => {
        const card = el.closest('[class]');
        return card?.textContent?.replace(/\n/g, ' ').slice(0, 500) || '';
      });
      const hasNotAdvice = cardText.toLowerCase().includes('not investment advice') || cardText.toLowerCase().includes('education');
      console.log('F2_Q1_NOT_ADVICE:' + hasNotAdvice + ' TEXT:' + cardText.slice(0, 300));

      // Ask advice question — should be refused or redirected
      await qInput.fill('Should I buy more large cap funds?');
      await sendBtn.click();
      console.log('F2_Q2_SENT');
      await p.waitForSelector('textarea:not([disabled])', { timeout: 90000 });
      await p.screenshot({ path: SS_DIR + '/f2-refusal.png' });
      const refText = await assistantTitle.evaluate(el => {
        const card = el.closest('[class]');
        return card?.textContent?.replace(/\n/g, ' ').slice(0, 500) || '';
      });
      console.log('F2_Q2_TEXT:' + refText.slice(0, 300));
    } catch (e) {
      console.log('F2_ANSWER_TIMEOUT:' + e.message.slice(0, 100));
      await p.screenshot({ path: SS_DIR + '/f2-timeout.png' });
    }
  } else {
    console.log('F2_ASSISTANT_NOT_FOUND');
  }

  // ── A4 / B4: Mobile viewport ──────────────────────────────────────────────
  await p.setViewportSize({ width: 390, height: 844 });
  await p.goto(REPORT_URL);
  await p.waitForSelector(REPORT_READY, { timeout: 30000 });
  await p.waitForTimeout(300);

  // B4: At page top, sticky bar should be hidden (SummaryRow is visible)
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.waitForTimeout(500);
  await p.screenshot({ path: SS_DIR + '/b4-top.png' });
  const stickyAtTop = await p.evaluate(() => {
    const bars = document.querySelectorAll('.fixed.transition-transform');
    return [...bars].map(el => ({
      ariaHidden: el.getAttribute('aria-hidden'),
      classHasTranslateNeg: el.className.includes('-translate-y-full'),
      classHasTranslate0: el.className.includes('translate-y-0'),
    }));
  });
  console.log('B4_AT_TOP:' + JSON.stringify(stickyAtTop));

  // Scroll past the SummaryRow (KPI cards ~200px)
  await p.evaluate(() => window.scrollBy(0, 500));
  await p.waitForTimeout(700);
  await p.screenshot({ path: SS_DIR + '/b4-scrolled.png' });
  const stickyAfterScroll = await p.evaluate(() => {
    const bars = document.querySelectorAll('.fixed.transition-transform');
    return [...bars].map(el => ({
      ariaHidden: el.getAttribute('aria-hidden'),
      classHasTranslateNeg: el.className.includes('-translate-y-full'),
      classHasTranslate0: el.className.includes('translate-y-0'),
    }));
  });
  console.log('B4_AFTER_SCROLL:' + JSON.stringify(stickyAfterScroll));

  // A4: Why? button on mobile — check height + classes
  const pillBtn = p.locator('button:has-text("Why?")').first();
  if (await pillBtn.count() > 0) {
    const box = await pillBtn.boundingBox();
    const cls = await pillBtn.getAttribute('class') || '';
    console.log('A4_HEIGHT:' + (box?.height || 0) + ' A4_WIDTH:' + (box?.width || 0) + ' A4_CLASS:' + cls);
    await p.screenshot({ path: SS_DIR + '/a4-mobile.png' });
  }

  console.log('ALL_DONE');
  await b.close();
})().catch(async e => {
  console.error('FATAL:' + e.message.slice(0, 200));
  process.exit(1);
});
