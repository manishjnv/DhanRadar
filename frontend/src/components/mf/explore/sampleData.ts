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

// S1 hero quick actions, S2 search tags, and S3 quick-discovery chips are now
// ALL rendered from the shared QUICK_INTENTS registry (features/mf/quickIntents.ts,
// Phase C chip consolidation) — no page-local decorative chip vocabularies here.

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

// ── S5 AI discovery types (still used by LaneCards.tsx) ──
export interface DiscoveryRow { name: string; logo: string; color: string; val: string }
export interface DiscoveryLane { icon: string; tag: string; bg: string; color: string; rows: DiscoveryRow[] }

// ── S18 FAQ (6) ──
export const FAQ: { q: string; a: string }[] = [
  { q:'What do the fund labels mean?', a:'Each fund carries an educational assessment — In Form, On Track, Off Track, Out of Form, or Insufficient Data — from a fixed rule table. They describe how a fund has been tracking; they are not buy, sell, or hold advice.' },
  { q:'What is the confidence band?', a:'High, Medium, or Low tells you how much data supports the assessment. It is shown only as a word, never as a precise number.' },
  { q:'How is the rank decided?', a:'Within each SEBI category, funds are placed in an ordinal order by a market-wide model that refreshes nightly. Ranks are not comparable across categories and are not a recommendation.' },
  { q:'What returns are shown?', a:'Point-to-point returns from published NAV. Past performance does not guarantee future returns, and returns alone do not capture risk.' },
  { q:'Why does SIP return matter?', a:'Most investors invest monthly. SIP XIRR reflects the return a disciplined monthly investor would have earned, accounting for rupee-cost averaging.' },
  { q:'Is any of this investment advice?', a:'No. DhanRadar is an educational research platform, not a SEBI-registered investment adviser. For decisions specific to you, consult a registered adviser and read all scheme documents.' },
];
