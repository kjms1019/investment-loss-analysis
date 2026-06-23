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
