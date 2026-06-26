export type Severity = "none" | "weak" | "moderate" | "strong";

export interface Finding {
  type: "revenge" | "overtrading" | "disposition";
  label: string;
  detected: boolean;
  severity: Severity;
  metrics: Record<string, number | string | null>;
  evidence: string[];
  reference: string;
}

export interface Diagnosis {
  engine: string;
  headline: string;
  body: string;
  per_type: Record<
    string,
    { label: string; severity: Severity; summary: string; correction: string }
  >;
  llm_error?: string;
}

export interface Summary {
  trade_count: number;
  period_start: string;
  period_end: string;
  cycle_count: number;
  closed_cycle_count: number;
  win_count: number;
  loss_count: number;
  total_realized_pnl: number;
}

export interface Cycle {
  code: string;
  name: string;
  entry_time: string;
  exit_time: string | null;
  invested: number;
  realized_pnl: number;
  return_pct: number;
  holding_min: number | null;
  closed: boolean;
  is_win: boolean;
}

export interface Report {
  scenario: string;
  label: string;
  summary: Summary;
  findings: Finding[];
  diagnosis: Diagnosis;
  cycles: Cycle[];
}

// ── 새 파이프라인: 손실선별 → 심리 귀속 라우팅 ──────────────────────────
export type PsychType = "revenge" | "overtrading" | "disposition";

export interface LossSignal {
  score: number;
  evidence: string[];
}

export interface LossRow {
  code: string;
  name: string;
  entry_time: string;
  return_pct: number;
  r_mkt_pct: number | null;
  alpha_pct: number | null;
  tier: number | null;
  holding_min: number | null;
  dominant: PsychType | null;
  signals: Record<PsychType, LossSignal>;
  correction: string;
}

export interface Flow {
  scenario: string;
  label: string;
  screening: {
    closed: number;
    tier1: number;
    tier2: number;
    market_driven_excluded: number;
    selected: number;
  };
  routing: Record<PsychType | "other", number>;
  losses: LossRow[];
}
