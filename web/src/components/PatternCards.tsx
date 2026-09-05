import type { Finding } from "@/lib/types";
import { EvidenceList, FaceBar, SeverityBadge, Stat } from "./ui";

function num(m: Finding["metrics"], k: string): number {
  const v = m[k];
  return typeof v === "number" ? v : 0;
}

function CardShell({
  finding,
  emoji,
  axis,
  children,
}: {
  finding: Finding;
  emoji: string;
  axis: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-[var(--border)] bg-[var(--panel)] p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg">{emoji}</span>
            <h3 className="text-base font-bold text-slate-100">{finding.label}</h3>
          </div>
          <p className="mt-0.5 text-[11px] uppercase tracking-wide text-slate-500">{axis}</p>
        </div>
        <SeverityBadge severity={finding.severity} />
      </div>
      {children}
      <div>
        <EvidenceList items={finding.evidence} />
        <p className="mt-3 border-t border-[var(--border)] pt-2 text-[11px] leading-snug text-slate-500">
          📚 {finding.reference}
        </p>
      </div>
    </div>
  );
}

export function RevengeCard({ finding }: { finding: Finding }) {
  const m = finding.metrics;
  return (
    <CardShell finding={finding} emoji="🔥" axis="결정 · 시간 축">
      <div className="grid grid-cols-2 gap-2">
        <Stat label="리벤지 신호" value={num(m, "signal_count")} sub={`임계 ${num(m, "window_min")}분`} />
        <Stat label="강 신호" value={num(m, "strong_count")} tone={num(m, "strong_count") ? "neg" : "default"} />
      </div>
      <div className="flex gap-1.5 text-[11px]">
        <span className="rounded bg-rose-500/15 px-2 py-1 text-rose-300">강 {num(m, "strong_count")}</span>
        <span className="rounded bg-amber-500/15 px-2 py-1 text-amber-300">중 {num(m, "moderate_count")}</span>
        <span className="rounded bg-yellow-500/15 px-2 py-1 text-yellow-200">약 {num(m, "weak_count")}</span>
      </div>
    </CardShell>
  );
}

export function OvertradingCard({ finding }: { finding: Finding }) {
  const m = finding.metrics;
  const turnover = num(m, "annual_turnover_pct");
  const thr = num(m, "threshold_pct");
  const ratio = Math.min(100, (turnover / (thr * 4)) * 100); // 1000%를 풀스케일로
  const over = turnover >= thr;
  return (
    <CardShell finding={finding} emoji="🔁" axis="결정 · 빈도 축">
      <div>
        <div className="mb-1 flex justify-between text-xs">
          <span className="text-slate-400">연 환산 회전율</span>
          <span className={`font-bold tabular-nums ${over ? "text-rose-300" : "text-slate-200"}`}>
            {turnover.toLocaleString()}%
          </span>
        </div>
        <div className="relative h-2.5 overflow-hidden rounded-full bg-black/30">
          <div
            className={`h-full rounded-full ${over ? "bg-rose-400/80" : "bg-emerald-400/80"}`}
            style={{ width: `${ratio}%` }}
          />
          <div className="absolute top-0 h-full w-px bg-amber-300/80" style={{ left: `${(thr / (thr * 4)) * 100}%` }} />
        </div>
        <div className="mt-1 text-[11px] text-slate-500">
          임계선 {thr}% (Barber &amp; Odean 과매매 분위 ≈ 258%)
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Stat label="총 거래" value={num(m, "total_trades")} sub={`${num(m, "period_days")}일`} />
        <Stat label="최다 거래월" value={num(m, "busiest_month_trades")} sub={`평소 ×${num(m, "freq_multiple")}`} />
      </div>
    </CardShell>
  );
}

export function DispositionCard({ finding }: { finding: Finding }) {
  const m = finding.metrics;
  const pgr = num(m, "pgr");
  const plr = num(m, "plr");
  const gap = num(m, "pgr_minus_plr");
  const winHold = num(m, "avg_win_hold_min");
  const lossHold = num(m, "avg_loss_hold_min");
  return (
    <CardShell finding={finding} emoji="⚖️" axis="포지션 · 보유기간 축">
      <FaceBar leftLabel="PGR (이익실현)" leftValue={pgr} rightLabel="PLR (손실실현)" rightValue={plr} max={1} />
      <div className="grid grid-cols-2 gap-2">
        <Stat
          label="PGR − PLR"
          value={`${gap > 0 ? "+" : ""}${gap.toFixed(2)}`}
          tone={gap > 0 ? "neg" : "default"}
          sub={gap > 0 ? "처분효과 양(+)" : "역방향"}
        />
        <Stat
          label="보유기간 비"
          value={winHold ? `×${(lossHold / winHold).toFixed(1)}` : "-"}
          sub="손실/수익"
          tone={lossHold > winHold ? "neg" : "default"}
        />
      </div>
    </CardShell>
  );
}

export function PatternCard({ finding }: { finding: Finding }) {
  if (finding.type === "revenge") return <RevengeCard finding={finding} />;
  if (finding.type === "overtrading") return <OvertradingCard finding={finding} />;
  return <DispositionCard finding={finding} />;
}
