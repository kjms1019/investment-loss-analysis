import type { Flow, LossRow, PsychType } from "@/lib/types";
import { TYPE_META } from "@/lib/flow";

const TYPES: (PsychType | "other")[] = ["revenge", "overtrading", "disposition", "other"];

function pct(x: number | null) {
  return x == null ? "—" : `${x > 0 ? "+" : ""}${x.toFixed(2)}%`;
}
function hold(m: number | null) {
  if (m == null) return "—";
  return m >= 1440 ? `${(m / 1440).toFixed(1)}일` : `${Math.round(m)}분`;
}

function Funnel({ s }: { s: Flow["screening"] }) {
  const step = (n: number, label: string, sub: string, tone: string) => (
    <div className="flex-1 rounded-xl border border-[var(--border)] bg-black/20 px-4 py-3 text-center">
      <div className={`text-2xl font-bold tabular-nums ${tone}`}>{n}</div>
      <div className="text-xs font-medium text-slate-300">{label}</div>
      <div className="text-[11px] text-slate-500">{sub}</div>
    </div>
  );
  return (
    <div className="flex items-center gap-2">
      {step(s.closed, "청산 거래", "전체 라운드트립", "text-slate-100")}
      <span className="text-slate-600">→</span>
      {step(s.selected, "복기 대상", `1순위 ${s.tier1} · 2순위 ${s.tier2}`, "text-rose-300")}
      <span className="text-slate-600">/</span>
      {step(s.market_driven_excluded, "시장탓 제외", "α≥0 (네 탓 아님)", "text-slate-400")}
    </div>
  );
}

function Routing({ routing }: { routing: Flow["routing"] }) {
  const max = Math.max(1, ...TYPES.map((t) => routing[t] ?? 0));
  return (
    <div className="space-y-2">
      {TYPES.map((t) => {
        const m = TYPE_META[t];
        const n = routing[t] ?? 0;
        return (
          <div key={t} className="flex items-center gap-3">
            <div className={`w-24 shrink-0 text-xs font-medium ${m.text}`}>{m.label}</div>
            <div className="h-4 flex-1 overflow-hidden rounded bg-black/30">
              <div className={`h-full rounded ${m.bar}`} style={{ width: `${(n / max) * 100}%` }} />
            </div>
            <div className="w-10 shrink-0 text-right text-sm tabular-nums text-slate-300">{n}건</div>
          </div>
        );
      })}
    </div>
  );
}

function LossCard({ loss }: { loss: LossRow }) {
  const m = TYPE_META[loss.dominant ?? "other"];
  const dom = loss.dominant;
  return (
    <div className={`rounded-2xl border border-[var(--border)] bg-[var(--panel)] p-4 ring-1 ${m.ring}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="font-bold text-slate-100">{loss.name}</span>
          {loss.tier && (
            <span className="ml-2 rounded bg-black/30 px-1.5 py-0.5 text-[10px] text-slate-400">
              {loss.tier === 1 ? "1순위" : "2순위"}
            </span>
          )}
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${m.bg} ${m.text} ${m.ring}`}>
          {m.label}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-4 gap-1.5 text-center">
        {[
          ["실현", pct(loss.return_pct), loss.return_pct < 0 ? "text-rose-300" : "text-emerald-300"],
          ["시장", pct(loss.r_mkt_pct), "text-slate-300"],
          ["α", pct(loss.alpha_pct), "text-rose-300"],
          ["보유", hold(loss.holding_min), "text-slate-300"],
        ].map(([k, v, tone]) => (
          <div key={k as string} className="rounded-lg bg-black/20 px-1 py-1.5">
            <div className="text-[10px] uppercase text-slate-500">{k}</div>
            <div className={`text-sm font-bold tabular-nums ${tone}`}>{v}</div>
          </div>
        ))}
      </div>

      {dom ? (
        <>
          <ul className="mt-3 space-y-1">
            {loss.signals[dom].evidence.map((e, i) => (
              <li key={i} className="flex gap-1.5 text-[13px] leading-snug text-slate-300">
                <span className={`mt-1.5 h-1 w-1 shrink-0 rounded-full ${m.bar}`} />
                <span>{e}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2.5 border-t border-[var(--border)] pt-2 text-[12px] leading-snug text-emerald-300/90">
            ✎ {loss.correction}
          </p>
        </>
      ) : (
        <p className="mt-3 text-[13px] text-slate-500">
          심리 패턴 없음 → 진입오류·손절실패 에이전트로 라우팅될 케이스.
        </p>
      )}
    </div>
  );
}

export function FlowView({ flow }: { flow: Flow }) {
  return (
    <div className="space-y-6">
      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-300">1단계 · 시장 제거 손실 선별</h2>
        <Funnel s={flow.screening} />
        <p className="mt-2 text-[11px] text-slate-500">
          절대손익이 아니라 초과수익(α = 단순보유 − 시장)으로 &ldquo;시장 탓&rdquo;을 걷어내고 복기 대상만 추립니다.
        </p>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-300">2단계 · 심리 유형 귀속 (라우팅)</h2>
        <Routing routing={flow.routing} />
        <p className="mt-2 text-[11px] text-slate-500">
          각 손실 거래의 dominant 유형 = 다중분류기가 보낼 에이전트. &lsquo;기타&rsquo;는 진입/손절 에이전트행.
        </p>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-300">
          손실 거래별 귀속 진단 ({flow.losses.length}건)
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {flow.losses.map((l, i) => (
            <LossCard key={i} loss={l} />
          ))}
        </div>
      </section>
    </div>
  );
}
