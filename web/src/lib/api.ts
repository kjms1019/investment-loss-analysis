// 백엔드 FastAPI(analysis.api.main) 호출 클라이언트.
// 화면 ③④⑤⑥ 은 이 데이터를 그대로 렌더한다.

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export type DomainId = "entry" | "cut";

export interface UserItem { id: string; name: string; }

export interface TypeCard {
  id: DomainId; name: string; def: string; count: number; amount: number;
  color: string; tint: string; psychLabel: string;
}
export interface DistItem { id: DomainId; name: string; color: string; psych: string; count: number; amount: number; }

// 빈도+총손실금 상호작용 (백엔드 _interaction_dto 와 1:1)
export interface InteractionStat { count: number; amount: number; }
export interface InteractionOption {
  basis: "frequency" | "amount"; label: string; type: DomainId; name: string; count: number; amount: number;
}
export interface Interaction {
  stats: Record<DomainId, InteractionStat>;
  frequency_winner: DomainId;
  amount_winner: DomainId;
  question_required: boolean;
  message: string;
  auto_selected: DomainId | null;
  options: InteractionOption[];
}

export interface Dashboard {
  user_id: string;
  total_loss_trades: number;
  counts: { entry: number; cut: number };
  avg_score: number | null;
  dominant: { id: DomainId; name: string; count: number };
  typeCards: TypeCard[];
  dist: DistItem[];
  interaction: Interaction;
}

export interface TradeChart {
  series: { t: string; c: number }[];
  entry: { i: number; t: string; price: number };
  exit: { i: number; t: string; price: number };
  stop: number | null;
  breach: { i: number; t: string } | null;
  mae: { i: number; t: string; price: number } | null;
  lo: number; hi: number;
  pnl_pct: number | null; label: string;
}

export interface Trade {
  trade_id: string; code: string; name: string; date: string;
  type: DomainId; typeName: string; sev: "weak" | "moderate" | "strong";
  label: string; desc: string; evidence: string[];
  eScore: number | null; cScore: number | null; route: string | null; conf: number | null;
  score: number | null; loss: number | null;
  signals: { 확대: number | null; 지연: number | null; 물타기: number | null } | null;
  chart: TradeChart | null;
  why: { text: string; strong: boolean }[];
  psych: { name: string; desc: string; detected: boolean; score: number | null; evidence: string[] } | null;
}

// 분석 차트용 전체 거래(이익+손실). type=null 이면 이익·비선별 거래.
export interface AllTrade { code: string; name: string; date: string; pnl: number; type: DomainId | null; }

export interface Pattern {
  type: DomainId; typeName: string; color: string; tint: string;
  title: string; stat: string; tag: string; example: string; correction: string;
}

export interface DispSig {
  key: string; domain: DomainId; label: string; count: number;
  user_pct: number; pop_pct: number; ratio: number; reliable: boolean; solution: string;
}
export interface Disposition {
  user_id: string; total: number;
  dominant: { id: DomainId; name: string; pct: number };
  counts: { cut: number; entry: number };
  headline: string;
  signature: DispSig[];
  psych: { disposition: { user_pct: number; pop_pct: number }; revenge: { user_pct: number; pop_pct: number } };
  solutions: string[];
}

export interface Alert {
  kind: string; type: DomainId; title: string; body: string;
  name?: string; code?: string; risk: number; level?: string;
  reasons: string[]; basis: string;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  base: BASE,
  users: () => get<UserItem[]>(`/api/users`),
  dashboard: (u: string) => get<Dashboard>(`/api/dashboard/${encodeURIComponent(u)}`),
  trades: (u: string) => get<{ trades: Trade[]; count: number }>(`/api/trades/${encodeURIComponent(u)}`),
  allTrades: (u: string) => get<{ trades: AllTrade[]; count: number }>(`/api/all-trades/${encodeURIComponent(u)}`),
  profile: (u: string) => get<{ patterns: Pattern[] }>(`/api/profile/${encodeURIComponent(u)}`),
  disposition: (u: string) => get<Disposition>(`/api/disposition/${encodeURIComponent(u)}`),
  alerts: (u: string) => get<{ alerts: Alert[] }>(`/api/alerts/${encodeURIComponent(u)}`),
};
