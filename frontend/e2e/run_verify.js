const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const OTP_FILE = 'C:/Users/manis/AppData/Local/Temp/dhanradar_otp.txt';
const SS_DIR = path.resolve(__dirname, '../../docs/research/verify-screenshots');
const CAS_FILE = path.resolve(__dirname, '../../docs/cas_cams.pdf');
const PRE_OTP = process.env.TEST_OTP || '';

if (fs.existsSync(OTP_FILE)) fs.unlinkSync(OTP_FILE);

// Reliable "report is done loading" selector — SummaryRow has "Total invested" text
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
  console.log('LOGGED_IN:' + p.url());
  await p.screenshot({ path: SS_DIR + '/post-login.png' });

  // ── NAVIGATE TO UPLOAD PAGE & USE EXISTING PORTFOLIO ────────────────────
  await p.goto('https://dhanradar.com/mf/upload');
  await p.waitForLoadState('networkidle');
  await p.screenshot({ path: SS_DIR + '/upload-page.png' });

  // Click the "Default" existing portfolio card (PR #160 persistent holdings)
  const defaultCard = p.locator('a:has-text("Default"), [href*="/mf/report"]').first();
  let jobId = '';

  if (await defaultCard.count() > 0) {
    const href = await defaultCard.getAttribute('href') || '';
    console.log('DEFAULT_CARD_HREF:' + href);
    await defaultCard.click();
    await p.waitForURL(/\/mf\/report\//, { timeout: 15000 });
    jobId = p.url().split('/mf/report/')[1]?.split('?')[0] || '';
    console.log('REPORT_JOB_ID:' + jobId);
  } else {
    console.log('No default card found — uploading CAS');
    const uploadInput = p.locator('input[type="file"]');
    await uploadInput.setInputFiles(CAS_FILE);
    const analyzeBtn = p.locator('button:has-text("Analyze"), button:has-text("Generate report"), button:has-text("Upload")').first();
    if (await analyzeBtn.count() > 0) await analyzeBtn.click();
    await p.waitForURL(/\/mf\/report\//, { timeout: 180000 });
    jobId = p.url().split('/mf/report/')[1]?.split('?')[0] || '';
    console.log('REPORT_JOB_ID:' + jobId);
  }

  // ── A3: catch loading skeletons immediately on fresh navigation ──────────
  await p.goto('https://dhanradar.com/mf/report/' + jobId);
  await p.waitForTimeout(150);
  await p.screenshot({ path: SS_DIR + '/a3-skeletons.png' });
  const skeletonCount = await p.locator('[class*="animate-pulse"]').count();
  console.log('A3_SKELETON_COUNT:' + skeletonCount);

  // Wait for report to fully load
  await p.waitForSelector(REPORT_READY, { timeout: 60000 });
  console.log('REPORT_LOADED');
  await p.screenshot({ path: SS_DIR + '/report-desktop.png' });

  // ── B3: ProgressView — upload fresh CAS to see it ───────────────────────
  await p.goto('https://dhanradar.com/mf/upload');
  await p.waitForLoadState('networkidle');
  const up2 = p.locator('input[type="file"]');
  if (await up2.count() > 0) {
    await up2.setInputFiles(CAS_FILE);
    const btn2 = p.locator('button:has-text("Analyze"), button:has-text("Generate report"), button:has-text("Upload")').first();
    if (await btn2.count() > 0) await btn2.click();
    try {
      await p.waitForURL(/\/mf\/report\//, { timeout: 10000 });
      await p.waitForTimeout(600);
      await p.screenshot({ path: SS_DIR + '/b3-progress.png' });
      const svgRing = await p.locator('svg.animate-spin').count();
      const tipCount = await p.locator('text=/Reading|Computing|Analysing|Preparing/').count();
      console.log('B3_SVG_RING:' + svgRing + ' B3_TIP_COUNT:' + tipCount);
      // wait for the new report to finish loading
      await p.waitForSelector(REPORT_READY, { timeout: 120000 });
      jobId = p.url().split('/mf/report/')[1]?.split('?')[0] || jobId;
    } catch (e) {
      console.log('B3_TIMEOUT:' + e.message);
    }
  }

  // ── Navigate to settled report for remaining checks ─────────────────────
  await p.setViewportSize({ width: 1280, height: 800 });
  await p.goto('https://dhanradar.com/mf/report/' + jobId);
  await p.waitForSelector(REPORT_READY, { timeout: 60000 });
  await p.screenshot({ path: SS_DIR + '/report-full.png', fullPage: true });

  // ── A1: WhyThisLabelPanel — no inline color/bg styles ───────────────────
  const inlineStyles = await p.evaluate(() =>
    Array.from(document.querySelectorAll('[style]'))
      .filter(el => {
        const s = el.style;
        return s.color || s.backgroundColor || s.fontSize;
      })
      .map(el => (el.className?.toString?.() || '').slice(0, 60) + ' | ' + el.getAttribute('style'))
  );
  console.log('A1_INLINE_COLOR_STYLES:' + JSON.stringify(inlineStyles.slice(0, 8)));

  // ── A2: Why? accordion open/close transition (grid-rows-[1fr]) ───────────
  const whyBtn = p.locator('button:has-text("Why?")').first();
  const whyCount = await whyBtn.count();
  console.log('A2_WHY_BTN_COUNT:' + whyCount);
  if (whyCount > 0) {
    await whyBtn.click();
    await p.waitForTimeout(300);
    await p.screenshot({ path: SS_DIR + '/a2-why-open.png' });
    // Check the accordion div has grid-rows-[1fr] (open state)
    const openClass = await p.evaluate(() => {
      const els = Array.from(document.querySelectorAll('[class]'));
      return els.filter(el => el.className?.includes?.('grid-rows-[1fr]')).map(el => el.className?.toString?.().slice(0, 80)).join('|');
    });
    console.log('A2_OPEN_CLASS:' + openClass.slice(0, 200));
    await whyBtn.click();
    await p.waitForTimeout(300);
    await p.screenshot({ path: SS_DIR + '/a2-why-closed.png' });
    const closedClass = await p.evaluate(() => {
      const els = Array.from(document.querySelectorAll('[class]'));
      return els.filter(el => el.className?.includes?.('grid-rows-[0fr]')).map(el => el.className?.toString?.().slice(0, 80)).join('|');
    });
    console.log('A2_CLOSED_CLASS:' + closedClass.slice(0, 200));
  }

  // ── D1: Concentration callout ────────────────────────────────────────────
  const concEl = p.locator('text=Concentration').first();
  console.log('D1_CONCENTRATION_COUNT:' + await concEl.count());
  if (await concEl.count() > 0) {
    const txt = await concEl.evaluate(el => el.closest('.mt-4')?.textContent?.replace(/\n/g, ' ').slice(0, 200) || '');
    console.log('D1_TEXT:' + txt);
  }
  await p.screenshot({ path: SS_DIR + '/d1-concentration.png' });

  // ── D2: Portfolio Overlap section ────────────────────────────────────────
  await p.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await p.waitForTimeout(400);
  await p.screenshot({ path: SS_DIR + '/d2-overlap.png' });
  const overlapTitle = p.locator('text=Portfolio Overlap').first();
  console.log('D2_OVERLAP_COUNT:' + await overlapTitle.count());
  if (await overlapTitle.count() > 0) {
    const txt = await overlapTitle.evaluate(el => el.closest('section, div[class]')?.textContent?.replace(/\n/g, ' ').slice(0, 300) || '');
    console.log('D2_TEXT:' + txt.slice(0, 200));
  }

  // ── F2: Research Assistant ────────────────────────────────────────────────
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.waitForTimeout(300);
  const assistantTitle = p.locator('text=Portfolio Research Assistant').first();
  console.log('F2_ASSISTANT_COUNT:' + await assistantTitle.count());
  if (await assistantTitle.count() > 0) {
    await p.screenshot({ path: SS_DIR + '/f2-assistant.png' });
    // Find the form within the assistant card
    const form = p.locator('form').first();
    const qInput = form.locator('input, textarea').first();
    await qInput.fill('What is the largest category in my portfolio?');
    const sendBtn = form.locator('button[type="submit"]').first();
    await sendBtn.click();
    console.log('F2_QUESTION_SENT');
    await p.waitForTimeout(20000);
    await p.screenshot({ path: SS_DIR + '/f2-answer.png' });
    const ansText = await assistantTitle.evaluate(el => {
      const card = el.closest('[class]');
      return card?.textContent?.replace(/\n/g, ' ').slice(0, 400) || '';
    });
    const hasNotAdvice = ansText.toLowerCase().includes('not investment advice') || ansText.toLowerCase().includes('education');
    console.log('F2_NOT_ADVICE:' + hasNotAdvice + ' LEN:' + ansText.length);

    // Advice refusal
    await qInput.fill('Should I buy more large cap funds?');
    await sendBtn.click();
    await p.waitForTimeout(20000);
    await p.screenshot({ path: SS_DIR + '/f2-refusal.png' });
    const refText = await assistantTitle.evaluate(el => {
      const card = el.closest('[class]');
      return card?.textContent?.replace(/\n/g, ' ').slice(0, 400) || '';
    });
    console.log('F2_REFUSAL_TEXT:' + refText.slice(0, 200));
  }

  // ── B1/B2: Stagger + count-up — navigate fresh ───────────────────────────
  await p.goto('https://dhanradar.com/mf/report/' + jobId);
  await p.waitForTimeout(300);
  await p.screenshot({ path: SS_DIR + '/b1b2-early.png' });
  await p.waitForSelector(REPORT_READY, { timeout: 30000 });
  const fadeElCount = await p.locator('[class*="animate-fade"], [class*="FadeUp"], [class*="fade-up"]').count();
  console.log('B1_FADE_COUNT:' + fadeElCount);
  await p.screenshot({ path: SS_DIR + '/b1b2-loaded.png' });

  // ── A4 / B4: Mobile viewport ──────────────────────────────────────────────
  await p.setViewportSize({ width: 390, height: 844 });
  await p.goto('https://dhanradar.com/mf/report/' + jobId);
  await p.waitForSelector(REPORT_READY, { timeout: 30000 });
  await p.screenshot({ path: SS_DIR + '/a4-b4-mobile-top.png' });

  // A4: Why? pill tap target on mobile
  const pillBtn = p.locator('button:has-text("Why?")').first();
  if (await pillBtn.count() > 0) {
    const box = await pillBtn.boundingBox();
    const cls = await pillBtn.getAttribute('class') || '';
    console.log('A4_HEIGHT:' + (box?.height || 0) + ' A4_CLASS:' + cls.slice(0, 120));
  }

  // B4: Scroll to trigger sticky bar
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.waitForTimeout(400);
  // Sticky bar should be HIDDEN initially (SummaryRow is visible)
  const stickyHidden = await p.evaluate(() => {
    const bars = Array.from(document.querySelectorAll('.fixed'));
    return bars.some(el => el.getAttribute('aria-hidden') === 'true' && el.classList.contains('transition-transform'));
  });
  console.log('B4_STICKY_HIDDEN_INITIALLY:' + stickyHidden);

  // Scroll past the SummaryRow (KPI cards are at top, ~200px tall)
  await p.evaluate(() => window.scrollBy(0, 400));
  await p.waitForTimeout(600);
  await p.screenshot({ path: SS_DIR + '/b4-after-scroll.png' });
  const stickyShown = await p.evaluate(() => {
    const bars = Array.from(document.querySelectorAll('.fixed'));
    return bars.some(el => el.getAttribute('aria-hidden') === 'false' && el.classList.contains('transition-transform'));
  });
  console.log('B4_STICKY_VISIBLE_AFTER_SCROLL:' + stickyShown);

  // Scroll back and check it hides again
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.waitForTimeout(600);
  await p.screenshot({ path: SS_DIR + '/b4-scrolled-back.png' });

  console.log('ALL_DONE');
  await b.close();
})().catch(async e => {
  console.error('FATAL:' + e.message);
  process.exit(1);
});
