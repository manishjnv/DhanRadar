// frontend/src/features/signal/types.ts

export type SignalState = 'triggered' | 'watch' | 'no_signal';

export interface SignalRules {
  nifty_threshold: number;
  vix_threshold: number;
  breadth_threshold: number;
  deploy_ladder: number[]; // exactly 5 entries summing to ≤100
  alerts_on: boolean;
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
