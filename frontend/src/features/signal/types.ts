// frontend/src/features/signal/types.ts

export type SignalState = 'triggered' | 'watch' | 'no_signal';

export interface SignalRules {
  nifty_threshold: number;
  vix_threshold: number;
  breadth_threshold: number;
  deploy_ladder: number[]; // exactly 5 entries summing to ≤100
  alerts_on: boolean;
  sip_day?: number | null;
  earned_achievements?: string[];
}

export interface SignalDipFund {
  balance: number;
  monthly_addition: number;
  last_updated: string; // ISO datetime
}

export interface SignalDeployment {
  id: string;
  date: string; // ISO date
  amount: number | null;
  signal_state: SignalState | null;
  market_snapshot: {
    nifty?: number;
    vix?: number;
    ad_ratio?: number;
  } | null;
  created_at: string;
}

export interface VIXData {
  value: number;
  change_pct: number;
  market_open: boolean;
}

export interface BreadthData {
  advances: number;
  declines: number;
  ad_ratio: number;
  market_open: boolean;
}

/** Derived client-side — never rendered as a numeric score in the DOM. */
export interface MarketSignalState {
  nifty_score: number;    // 0–4
  vix_score: number;      // 0–4
  breadth_score: number;  // 0–4
  weighted_score: number; // float 0–4 — NOT shown in DOM
  state: SignalState;
}

// ---------------------------------------------------------------------------
// Journal / Reflect tab (Phase 2)
// ---------------------------------------------------------------------------

export type JournalDecision = 'deployed' | 'watched' | 'skipped';
export type JournalEmotion = 'fearful' | 'calm' | 'excited' | 'fomo' | 'disciplined';

export interface JournalEntry {
  id: string;
  date: string;                   // ISO date
  decision: JournalDecision;
  amount_deployed: number | null;
  emotions: JournalEmotion[];
  notes: string | null;
  nifty_pct: number | null;
  vix_level: number | null;
  breadth_ratio: number | null;
  signal_state: SignalState | null;
  fomo_avoided: boolean | null;
  premature: boolean | null;
  created_at: string;
}

export interface BehaviourScores {
  discipline_score: number;   // 0–100 integer — user behaviour metric
  patience_score: number;     // 0–100 integer — user behaviour metric
  investor_score: number;     // 0–100 integer — composite behaviour metric
  trust_wins: number;
  trust_total: number;
  has_trust_data: boolean;    // false until 90 days of signals have elapsed
}

export interface JournalResponse {
  entries: JournalEntry[];
  behaviour: BehaviourScores;
}

export interface JournalEntryCreate {
  date: string;
  decision: JournalDecision;
  amount_deployed?: number | null;
  emotions: JournalEmotion[];
  notes?: string | null;
  nifty_pct?: number | null;
  vix_level?: number | null;
  breadth_ratio?: number | null;
}

// ---------------------------------------------------------------------------
// Learning content (Phase 3 Part A)
// ---------------------------------------------------------------------------

export interface LearningArticle {
  slug: string;
  title: string;
  read_min: number;
  link: string;
}

export interface LearningContentResponse {
  articles: LearningArticle[];
}

// ---------------------------------------------------------------------------
// Notifications (Phase 3 Part B)
// ---------------------------------------------------------------------------

export interface SignalNotification {
  id: string;
  message: string;
  signal_state: SignalState;
  created_at: string;
}

export interface NotificationsResponse {
  unread: SignalNotification[];
}
