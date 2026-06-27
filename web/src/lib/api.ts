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

export interface Trade {
  trade_id: string; code: string; name: string; date: string;
  type: DomainId; typeName: string; sev: "weak" | "moderate" | "strong";
  label: string; desc: string; evidence: string[];
  eScore: number | null; cScore: number | null; route: string | null; conf: number | null;
  score: number | null; loss: number | null;
  signals: { 확대: number | null; 지연: number | null; 물타기: number | null } | null;
}

export interface Pattern {
  type: DomainId; typeName: string; color: string; tint: string;
  title: string; stat: string; tag: string; example: string; correction: string;
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
  profile: (u: string) => get<{ patterns: Pattern[] }>(`/api/profile/${encodeURIComponent(u)}`),
  alerts: (u: string) => get<{ alerts: Alert[] }>(`/api/alerts/${encodeURIComponent(u)}`),
};
