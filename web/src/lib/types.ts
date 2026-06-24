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

// ── 하이브리드 에이전트: 진입오류+리벤지 / 손절실패+처분효과 ─────────────
export interface PsychAssignment {
  type_key: "revenge" | "disposition";
  target_agent_id: string;
  rationale: string;
  included: boolean;
}

export interface HybridAgent {
  agent_id: "entry_error_psych_hybrid" | "stop_loss_psych_hybrid";
  base_agent_id: "entry_error" | "stop_loss_failure";
  score: number;
  severity: Severity;
  summary: string;
  psych_assignments: PsychAssignment[];
  findings: Finding[];
  recommendations: string[];
}

export interface DiscardedPsychFeature {
  type: "overtrading";
  label: string;
  reason: string;
}

export interface HybridReport {
  scenario: string;
  label: string;
  agents: HybridAgent[];
  discarded_psych_features: DiscardedPsychFeature[];
}
