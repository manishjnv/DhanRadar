/**
 * Fund Explorer — illustrative ("preview") data for the V4 layout.
 *
 * IMPORTANT: this is SAMPLE data so every V4 section renders fully while the
 * real feeds/endpoints are built (founder call 2026-06-24: build all UI now,
 * wire data later). Sections fed by this module are marked "Preview" in the UI.
 *
 * COMPLIANCE — this data is deliberately scrubbed to the non-negotiables:
 *   - NO DhanRadar score number / grade / percentile (non-neg #2). Funds carry
 *     an educational LABEL + confidence BAND only.
 *   - NO advisory verbs (buy/sell/hold/avoid/caution) anywhere (non-neg #1).
 *   - Returns %, AUM ₹Cr, expense %, SIP XIRR %, drawdown %, riskometer band
 *     are FACTUAL data types, DOM-allowed (not the proprietary score).
 */
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';

// Decorative logo colours (data-viz palette; not brand CTA tokens).
export const C = {
  blue: '#1E5EFF', emerald: '#00B386', amber: '#F5A623', red: '#E5484D',
  orange: '#F97316', violet: '#8B5CF6', cyan: '#00C2FF', navy: '#0B1F3A',
} as const;

export interface SampleFund {
  isin: string;
  name: string;
  amc: string;
  short: string;
  logo: string;
  color: string;
  cat: string;
  sub: string;
  label: Label;
  band: ConfidenceBand;
  risk: 'Very Low' | 'Low' | 'Moderate' | 'Mod. High' | 'High' | 'Very High';
  r1: number; r3: number; r5: number;
  sipXirr: number;
  expense: number;
  aumCr: number;
  drawdown: number;
  flow: string;   // e.g. "+₹2,840 Cr"
  rankDelta: number;
  fit: 'Strong' | 'Good' | 'Moderate' | 'Limited';
}

// 12 illustrative funds (educational labels, no score numbers).
export const SAMPLE_FUNDS: SampleFund[] = [
  { isin:'S01', name:'Sample Small Cap Fund A', amc:'Sample AMC One', short:'Small Cap A', logo:'A', color:C.blue, cat:'Equity', sub:'Small Cap', label:'in_form', band:'high', risk:'High', r1:12.4, r3:28.6, r5:26.1, sipXirr:24.0, expense:0.42, aumCr:9840, drawdown:-28, flow:'+₹2,840 Cr', rankDelta:+1, fit:'Strong' },
  { isin:'S02', name:'Sample Small Cap Fund B', amc:'Sample AMC Two', short:'Small Cap B', logo:'B', color:C.emerald, cat:'Equity', sub:'Small Cap', label:'in_form', band:'high', risk:'High', r1:10.8, r3:27.1, r5:28.4, sipXirr:25.4, expense:0.68, aumCr:58200, drawdown:-31, flow:'+₹6,120 Cr', rankDelta:-1, fit:'Good' },
  { isin:'S03', name:'Sample Flexi Cap Fund A', amc:'Sample AMC Three', short:'Flexi Cap A', logo:'F', color:C.navy, cat:'Equity', sub:'Flexi Cap', label:'in_form', band:'high', risk:'Mod. High', r1:16.2, r3:22.4, r5:21.8, sipXirr:20.4, expense:0.62, aumCr:78420, drawdown:-19, flow:'+₹8,920 Cr', rankDelta:0, fit:'Strong' },
  { isin:'S04', name:'Sample Large Cap Fund A', amc:'Sample AMC Four', short:'Large Cap A', logo:'L', color:C.orange, cat:'Equity', sub:'Large Cap', label:'on_track', band:'high', risk:'Moderate', r1:13.4, r3:17.8, r5:16.4, sipXirr:16.0, expense:0.52, aumCr:68400, drawdown:-15, flow:'+₹5,640 Cr', rankDelta:+2, fit:'Strong' },
  { isin:'S05', name:'Sample Mid Cap Fund A', amc:'Sample AMC Five', short:'Mid Cap A', logo:'M', color:C.emerald, cat:'Equity', sub:'Mid Cap', label:'on_track', band:'medium', risk:'High', r1:12.8, r3:25.2, r5:25.6, sipXirr:23.4, expense:0.46, aumCr:42100, drawdown:-24, flow:'+₹3,140 Cr', rankDelta:+1, fit:'Good' },
  { isin:'S06', name:'Sample Value Fund A', amc:'Sample AMC Six', short:'Value A', logo:'V', color:C.blue, cat:'Equity', sub:'Value', label:'on_track', band:'high', risk:'Mod. High', r1:15.6, r3:28.2, r5:24.8, sipXirr:23.1, expense:0.62, aumCr:38600, drawdown:-21, flow:'+₹4,820 Cr', rankDelta:+2, fit:'Good' },
  { isin:'S07', name:'Sample ELSS Fund A', amc:'Sample AMC Seven', short:'ELSS A', logo:'E', color:C.cyan, cat:'ELSS', sub:'ELSS', label:'on_track', band:'medium', risk:'Mod. High', r1:13.8, r3:21.4, r5:20.8, sipXirr:19.6, expense:0.58, aumCr:24800, drawdown:-20, flow:'+₹2,640 Cr', rankDelta:+1, fit:'Strong' },
  { isin:'S08', name:'Sample Balanced Advantage Fund A', amc:'Sample AMC Eight', short:'Balanced Adv A', logo:'H', color:C.red, cat:'Hybrid', sub:'Balanced Adv.', label:'on_track', band:'high', risk:'Moderate', r1:11.2, r3:16.4, r5:14.8, sipXirr:14.2, expense:0.74, aumCr:94200, drawdown:-11, flow:'+₹6,420 Cr', rankDelta:0, fit:'Strong' },
  { isin:'S09', name:'Sample Index Fund A', amc:'Sample AMC Nine', short:'Index A', logo:'I', color:C.navy, cat:'Index', sub:'Index', label:'on_track', band:'high', risk:'Moderate', r1:11.8, r3:14.2, r5:13.9, sipXirr:13.4, expense:0.20, aumCr:18400, drawdown:-14, flow:'+₹1,420 Cr', rankDelta:0, fit:'Strong' },
  { isin:'S10', name:'Sample Thematic Fund A', amc:'Sample AMC Ten', short:'Thematic A', logo:'T', color:C.cyan, cat:'Equity', sub:'Thematic', label:'off_track', band:'medium', risk:'Very High', r1:19.6, r3:24.2, r5:26.8, sipXirr:24.1, expense:0.32, aumCr:11800, drawdown:-32, flow:'+₹1,240 Cr', rankDelta:+8, fit:'Moderate' },
  { isin:'S11', name:'Sample Sectoral Fund A', amc:'Sample AMC Eleven', short:'Sectoral A', logo:'S', color:C.orange, cat:'Equity', sub:'Sectoral', label:'off_track', band:'low', risk:'Very High', r1:17.8, r3:22.6, r5:28.1, sipXirr:25.2, expense:0.62, aumCr:13600, drawdown:-36, flow:'-₹640 Cr', rankDelta:-4, fit:'Limited' },
  { isin:'S12', name:'Sample Gold FOF A', amc:'Sample AMC Twelve', short:'Gold FOF A', logo:'G', color:C.amber, cat:'FOF', sub:'Gold FOF', label:'off_track', band:'medium', risk:'Moderate', r1:22.4, r3:16.8, r5:14.2, sipXirr:13.0, expense:0.34, aumCr:4200, drawdown:-12, flow:'-₹420 Cr', rankDelta:-2, fit:'Moderate' },
];

// ── S1 hero: illustrative stat tiles (real ones are filled by the page) ──
export const HERO_QUICK = [
  'Best SIP Funds', 'Best Funds Today', 'Top Rated', 'Lowest Risk', 'Highest Return',
  'Undervalued', 'New Investor Picks', 'Retirement Funds', 'Tax Saving',
];

// ── S2 search suggestion tags ──
export const SEARCH_TAGS = ['Small Cap', 'Large Cap', 'Healthcare', 'Best SIP', 'Low Risk', 'Tax Saving', 'Index Funds', 'Flexi Cap'];

// ── S3 quick-discovery chips (15) ──
export const DISCOVERY_CHIPS = [
  '🔥 Trending', '⭐ Top Rated', '💰 Highest SIP Return', '🛡 Lowest Risk', '📈 Momentum Leaders',
  '💎 Undervalued', '🚀 Fastest AUM', '🏆 Consistent', '🧠 AI Picks', '💸 Lowest Cost',
  '❤️ Beginner Friendly', '🎯 Retirement', '🏦 Tax Saving ELSS', '🌍 International', '📊 Index Funds',
];

// ── S4 advanced-filter groups + ranges ──
export const FILTER_GROUPS: { title: string; options: string[] }[] = [
  { title: 'Category', options: ['Equity','Debt','Hybrid','Index','ETF','ELSS','International','FOF','Solution'] },
  { title: 'Sub-category', options: ['Large Cap','Flexi Cap','Mid Cap','Small Cap','Multi Cap','Value','Contra','Focused','Sectoral','Thematic','Corporate Bond','Liquid','Balanced Adv.','Aggr. Hybrid'] },
  { title: 'Risk', options: ['Very Low','Low','Moderate','Mod. High','High','Very High'] },
  { title: 'Quality', options: ['Top quartile','Rank Top 5','High consistency','Strong manager','Strong AMC'] },
  { title: 'Market-phase fit', options: ['Best in Fear','Best in Recovery','Best in Bull','Best in Euphoria'] },
  { title: 'Portfolio', options: ['Low overlap','High large-cap','High mid-cap','High small-cap','Low cash','Diversified'] },
];
export const FILTER_RANGES: { title: string; min: string; mid: string; max: string }[] = [
  { title: '3Y / 5Y return (min %)', min: '0%', mid: '15%+', max: '35%' },
  { title: '5Y SIP XIRR (min %)', min: '0%', mid: '18%+', max: '30%' },
  { title: 'AUM (₹ Cr, min)', min: '0', mid: '5k+', max: '100k' },
  { title: 'Expense ratio (max %)', min: '0%', mid: '0.80%', max: '2.5%' },
];

// ── S5 AI discovery (4 lanes) ──
export interface DiscoveryRow { name: string; logo: string; color: string; val: string }
export interface DiscoveryLane { icon: string; tag: string; bg: string; color: string; rows: DiscoveryRow[] }
export const AI_DISCOVERY: DiscoveryLane[] = [
  { icon:'⚡', tag:'Improving fastest', bg:'rgba(0,179,134,.12)', color:C.emerald, rows:[
    { name:'Thematic A', logo:'T', color:C.cyan, val:'+11 rk' }, { name:'Small Cap A', logo:'A', color:C.blue, val:'+9 rk' }, { name:'Value A', logo:'V', color:C.blue, val:'+7 rk' }] },
  { icon:'📉', tag:'Losing momentum', bg:'rgba(229,72,77,.10)', color:C.red, rows:[
    { name:'Sectoral A', logo:'S', color:C.orange, val:'-4 rk' }, { name:'Intl A', logo:'N', color:C.violet, val:'-3 rk' }, { name:'Gold FOF A', logo:'G', color:C.amber, val:'-2 rk' }] },
  { icon:'🐋', tag:'Largest inflows', bg:'rgba(30,94,255,.10)', color:C.blue, rows:[
    { name:'Flexi Cap A', logo:'F', color:C.navy, val:'+₹8.9k Cr' }, { name:'Balanced Adv A', logo:'H', color:C.red, val:'+₹6.4k Cr' }, { name:'Small Cap B', logo:'B', color:C.emerald, val:'+₹6.1k Cr' }] },
  { icon:'🛡', tag:'Lower cost trend', bg:'rgba(245,166,35,.13)', color:C.amber, rows:[
    { name:'Value A', logo:'V', color:C.blue, val:'0.62%' }, { name:'Small Cap A', logo:'A', color:C.blue, val:'0.42%' }, { name:'ELSS A', logo:'E', color:C.cyan, val:'0.58%' }] },
];

// ── S9 category leaderboards (9) ──
export interface LeaderCard { cat: string; short: string; amc: string; logo: string; color: string; label: Label; band: ConfidenceBand; ret: string; risk: string; why: string }
export const LEADERBOARDS: LeaderCard[] = [
  { cat:'Best Large Cap', short:'Large Cap A', amc:'Sample AMC Four', logo:'L', color:C.orange, label:'on_track', band:'high', ret:'17.8%', risk:'Moderate', why:'Lowest drawdown in category with steady tracking.' },
  { cat:'Best Flexi Cap', short:'Flexi Cap A', amc:'Sample AMC Three', logo:'F', color:C.navy, label:'in_form', band:'high', ret:'22.4%', risk:'Mod. High', why:'Strong risk-adjusted history + broad diversification.' },
  { cat:'Best Mid Cap', short:'Mid Cap A', amc:'Sample AMC Five', logo:'M', color:C.emerald, label:'on_track', band:'medium', ret:'25.2%', risk:'High', why:'Consistent top-quartile placement.' },
  { cat:'Best Small Cap', short:'Small Cap A', amc:'Sample AMC One', logo:'A', color:C.blue, label:'in_form', band:'high', ret:'28.6%', risk:'High', why:'High returns with comparatively lower volatility.' },
  { cat:'Best ELSS', short:'ELSS A', amc:'Sample AMC Seven', logo:'E', color:C.cyan, label:'on_track', band:'medium', ret:'21.4%', risk:'Mod. High', why:'Low cost with a steady track record.' },
  { cat:'Best Hybrid', short:'Balanced Adv A', amc:'Sample AMC Eight', logo:'H', color:C.red, label:'on_track', band:'high', ret:'16.4%', risk:'Moderate', why:'Smoothest ride — shallow worst drawdown.' },
  { cat:'Best Debt', short:'Corp Bond A', amc:'Sample AMC Eight', logo:'H', color:C.red, label:'on_track', band:'high', ret:'7.6%', risk:'Low', why:'High-quality corporate bond portfolio.' },
  { cat:'Best Index', short:'Index A', amc:'Sample AMC Nine', logo:'I', color:C.navy, label:'on_track', band:'high', ret:'14.2%', risk:'Moderate', why:'Lowest tracking error at a 0.20% expense.' },
  { cat:'Best International', short:'Intl A', amc:'Sample AMC Eleven', logo:'N', color:C.violet, label:'off_track', band:'low', ret:'18.6%', risk:'High', why:'Cleanest global-tech exposure in the set.' },
];

// ── S10 DMMI ──
export const DMMI = {
  word: 'Cautiously Optimistic',
  sub: 'Accumulation phase · improving breadth',
  fill: 0.62, // visual arc only — NO number rendered
  best: [{ n:'Small Cap', d:'Strong inflows' }, { n:'Flexi Cap', d:'Best risk-adj' }, { n:'Healthcare', d:'Outperforming' }],
  weak: [{ n:'Gold FOF', d:'Losing flows' }, { n:'Intl Tech', d:'High valuations' }, { n:'Liquid', d:'Low real return' }],
  // Educational, NON-advisory framing (V4's "Suggested SIP/lumpsum action" reframed).
  notes: [
    { tone:'up' as const, title:'What disciplined SIPs have meant', body:'In comparable accumulation phases, regular monthly investing has historically smoothed entry prices versus one-time timing — an observation, not a recommendation.' },
    { tone:'info' as const, title:'How staggered entries behaved', body:'Spreading lump-sum entries across tranches has historically reduced timing risk in stretched markets. Outcomes vary; this is educational context only.' },
  ],
};

// ── S11 fund flow (3) ──
export const FUND_FLOW: DiscoveryLane[] = [
  { icon:'📥', tag:'Highest inflows', bg:'rgba(0,179,134,.12)', color:C.emerald, rows:[
    { name:'Flexi Cap A', logo:'F', color:C.navy, val:'+₹8.9k Cr' }, { name:'Balanced Adv A', logo:'H', color:C.red, val:'+₹6.4k Cr' }, { name:'Small Cap B', logo:'B', color:C.emerald, val:'+₹6.1k Cr' }, { name:'Large Cap A', logo:'L', color:C.orange, val:'+₹5.6k Cr' }] },
  { icon:'📤', tag:'Highest outflows', bg:'rgba(229,72,77,.10)', color:C.red, rows:[
    { name:'Sectoral A', logo:'S', color:C.orange, val:'-₹640 Cr' }, { name:'Intl A', logo:'N', color:C.violet, val:'-₹420 Cr' }, { name:'Legacy Debt A', logo:'D', color:'#64748B', val:'-₹310 Cr' }, { name:'Legacy Mid A', logo:'L', color:'#64748B', val:'-₹180 Cr' }] },
  { icon:'🚀', tag:'Fastest growing AUM', bg:'rgba(30,94,255,.10)', color:C.blue, rows:[
    { name:'Thematic A', logo:'T', color:C.cyan, val:'+52%' }, { name:'Small Cap A', logo:'A', color:C.blue, val:'+38%' }, { name:'Value A', logo:'V', color:C.blue, val:'+34%' }, { name:'ELSS A', logo:'E', color:C.cyan, val:'+29%' }] },
];

// ── S12 momentum ──
export interface MomRow { name: string; logo: string; color: string; val: string }
export const MOMENTUM: Record<'30d'|'90d'|'1y', { up: MomRow[]; down: MomRow[] }> = {
  '30d': { up:[{name:'Thematic A',logo:'T',color:C.cyan,val:'+11'},{name:'Small Cap A',logo:'A',color:C.blue,val:'+9'},{name:'Value A',logo:'V',color:C.blue,val:'+7'}], down:[{name:'Sectoral A',logo:'S',color:C.orange,val:'-4'},{name:'Intl A',logo:'N',color:C.violet,val:'-3'},{name:'Gold FOF A',logo:'G',color:C.amber,val:'-2'}] },
  '90d': { up:[{name:'Small Cap A',logo:'A',color:C.blue,val:'+14'},{name:'Thematic A',logo:'T',color:C.cyan,val:'+12'},{name:'Value A',logo:'V',color:C.blue,val:'+9'}], down:[{name:'Sectoral A',logo:'S',color:C.orange,val:'-7'},{name:'Intl A',logo:'N',color:C.violet,val:'-5'},{name:'Gold FOF A',logo:'G',color:C.amber,val:'-4'}] },
  '1y':  { up:[{name:'Thematic A',logo:'T',color:C.cyan,val:'+22'},{name:'Small Cap A',logo:'A',color:C.blue,val:'+18'},{name:'Value A',logo:'V',color:C.blue,val:'+11'}], down:[{name:'Sectoral A',logo:'S',color:C.orange,val:'-14'},{name:'Gold FOF A',logo:'G',color:C.amber,val:'-9'},{name:'Intl A',logo:'N',color:C.violet,val:'-6'}] },
};

// ── S13 consistency ──
export interface ConsRow { rank: number; name: string; logo: string; color: string; yrsBeat: string; stability: string; persistence: string; mgrChanges: string }
export const CONSISTENCY: ConsRow[] = [
  { rank:1, name:'Flexi Cap A', logo:'F', color:C.navy, yrsBeat:'9/10', stability:'Very High', persistence:'98%', mgrChanges:'0' },
  { rank:2, name:'Large Cap A', logo:'L', color:C.orange, yrsBeat:'9/10', stability:'Very High', persistence:'96%', mgrChanges:'0' },
  { rank:3, name:'Small Cap A', logo:'A', color:C.blue, yrsBeat:'8/10', stability:'High', persistence:'94%', mgrChanges:'0' },
  { rank:4, name:'Balanced Adv A', logo:'H', color:C.red, yrsBeat:'8/10', stability:'High', persistence:'95%', mgrChanges:'1' },
  { rank:5, name:'Mid Cap A', logo:'M', color:C.emerald, yrsBeat:'8/10', stability:'High', persistence:'92%', mgrChanges:'0' },
  { rank:6, name:'Value A', logo:'V', color:C.blue, yrsBeat:'7/10', stability:'High', persistence:'90%', mgrChanges:'1' },
];

// ── S14 low cost ──
export interface CostRow { rank: number; name: string; logo: string; color: string; expense: string; fee15y: string; retained: string; efficiency: string }
export const LOW_COST: CostRow[] = [
  { rank:1, name:'Index A', logo:'I', color:C.navy, expense:'0.20%', fee15y:'₹1.2 L', retained:'99%', efficiency:'High' },
  { rank:2, name:'Liquid A', logo:'E', color:C.emerald, expense:'0.18%', fee15y:'₹0.9 L', retained:'98%', efficiency:'High' },
  { rank:3, name:'Thematic A', logo:'T', color:C.cyan, expense:'0.32%', fee15y:'₹2.1 L', retained:'96%', efficiency:'Good' },
  { rank:4, name:'Corp Bond A', logo:'H', color:C.red, expense:'0.36%', fee15y:'₹1.8 L', retained:'97%', efficiency:'Good' },
  { rank:5, name:'Small Cap A', logo:'A', color:C.blue, expense:'0.42%', fee15y:'₹2.6 L', retained:'95%', efficiency:'Good' },
  { rank:6, name:'Balanced Adv A', logo:'H', color:C.red, expense:'0.42%', fee15y:'₹2.4 L', retained:'96%', efficiency:'Good' },
];

// ── S15 beginner picks (6) — educational framing, NO advisory verbs ──
export interface BeginnerCard { tag: string; color: string; short: string; logo: string; logoColor: string; why: string; suits: string; lessFor: string }
export const BEGINNER: BeginnerCard[] = [
  { tag:'First Fund', color:C.blue, short:'Flexi Cap A', logo:'F', logoColor:C.navy, why:'Diversified across the market with a relatively steady history.', suits:'First-time monthly investors.', lessFor:'Those wanting concentrated small-cap exposure.' },
  { tag:'Long Horizon', color:C.emerald, short:'Balanced Adv A', logo:'H', logoColor:C.red, why:'Auto-balances equity & debt for long-horizon compounding.', suits:'Those building a multi-decade corpus.', lessFor:'Those needing the money within ~2 years.' },
  { tag:'SIP-oriented', color:C.violet, short:'Small Cap A', logo:'A', logoColor:C.blue, why:'Strong SIP track record with disciplined risk control.', suits:'Disciplined monthly investors, 7yr+ horizon.', lessFor:'Short-horizon, lump-sum-only investors.' },
  { tag:'Tax Saving', color:C.amber, short:'ELSS A', logo:'E', logoColor:C.cyan, why:'80C-eligible with low cost and a steady record.', suits:'Salaried investors using the 80C limit.', lessFor:'Those needing liquidity before 3 years.' },
  { tag:'Conservative', color:C.cyan, short:'Corp Bond A', logo:'H', logoColor:C.red, why:'High-quality bonds with small drawdowns.', suits:'Capital-protection-first investors.', lessFor:'Those seeking double-digit returns.' },
  { tag:'Higher Risk', color:C.red, short:'Thematic A', logo:'T', logoColor:C.cyan, why:'Higher historical upside, but momentum-driven and volatile.', suits:'High-risk-appetite, 10yr+ horizons.', lessFor:'Anyone uneasy with a deep drawdown.' },
];

// ── S17 AI insights feed (6) — observations, NO directives ──
export const AI_FEED: string[] = [
  '**Small-cap funds** have been attracting the strongest inflows in 6 months, while their valuations have stretched.',
  '**Flexi-cap funds** currently show the steadiest risk-adjusted history in this sample.',
  '**Healthcare** rose the most in the rankings this month on earnings momentum.',
  '**Index expense ratios** keep falling — the cheapest large-cap exposure here is 0.20%.',
  '**Balanced-advantage funds** are seeing record inflows as participants hedge a stretched market.',
  '**Thematic funds** show top returns but also the deepest drawdowns in this sample.',
];

// ── S18 FAQ (6) ──
export const FAQ: { q: string; a: string }[] = [
  { q:'What do the fund labels mean?', a:'Each fund carries an educational assessment — In Form, On Track, Off Track, Out of Form, or Insufficient Data — from a fixed rule table. They describe how a fund has been tracking; they are not buy, sell, or hold advice.' },
  { q:'What is the confidence band?', a:'High, Medium, or Low tells you how much data supports the assessment. It is shown only as a word, never as a precise number.' },
  { q:'How is the rank decided?', a:'Within each SEBI category, funds are placed in an ordinal order by a market-wide model that refreshes nightly. Ranks are not comparable across categories and are not a recommendation.' },
  { q:'What returns are shown?', a:'Point-to-point returns from published NAV. Past performance does not guarantee future returns, and returns alone do not capture risk.' },
  { q:'Why does SIP return matter?', a:'Most investors invest monthly. SIP XIRR reflects the return a disciplined monthly investor would have earned, accounting for rupee-cost averaging.' },
  { q:'Is any of this investment advice?', a:'No. DhanRadar is an educational research platform, not a SEBI-registered investment adviser. For decisions specific to you, consult a registered adviser and read all scheme documents.' },
];
