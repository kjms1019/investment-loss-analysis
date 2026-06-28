import type { Severity } from "@/lib/types";

export const SEV_META: Record<
  Severity,
  { label: string; text: string; bg: string; ring: string; dot: string }
> = {
  strong: { label: "강", text: "text-rose-300", bg: "bg-rose-500/10", ring: "ring-rose-500/30", dot: "bg-rose-400" },
  moderate: { label: "중", text: "text-amber-300", bg: "bg-amber-500/10", ring: "ring-amber-500/30", dot: "bg-amber-400" },
  weak: { label: "약", text: "text-yellow-200", bg: "bg-yellow-500/10", ring: "ring-yellow-500/30", dot: "bg-yellow-300" },
  none: { label: "없음", text: "text-slate-400", bg: "bg-slate-500/10", ring: "ring-slate-600/30", dot: "bg-slate-500" },
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const m = SEV_META[severity];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${m.bg} ${m.text} ${m.ring}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${m.dot}`} />
      {m.label}
    </span>
  );
}

export function Stat({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  tone?: "default" | "pos" | "neg";
}) {
  const toneClass =
    tone === "pos" ? "text-emerald-300" : tone === "neg" ? "text-rose-300" : "text-slate-100";
  return (
    <div className="rounded-lg border border-[var(--border)] bg-black/20 px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-0.5 text-lg font-bold tabular-nums ${toneClass}`}>{value}</div>
      {sub && <div className="text-[11px] text-slate-500">{sub}</div>}
    </div>
  );
}

/** 두 값을 마주보게 비교하는 막대 (PGR vs PLR 등). */
export function FaceBar({
  leftLabel,
  leftValue,
  rightLabel,
  rightValue,
  max = 1,
}: {
  leftLabel: string;
  leftValue: number;
  rightLabel: string;
  rightValue: number;
  max?: number;
}) {
  const lp = Math.min(100, (leftValue / max) * 100);
  const rp = Math.min(100, (rightValue / max) * 100);
  return (
    <div className="space-y-2">
      <div>
        <div className="mb-1 flex justify-between text-xs">
          <span className="text-emerald-300">{leftLabel}</span>
          <span className="tabular-nums text-emerald-300">{leftValue.toFixed(2)}</span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-black/30">
          <div className="h-full rounded-full bg-emerald-400/80" style={{ width: `${lp}%` }} />
        </div>
      </div>
      <div>
        <div className="mb-1 flex justify-between text-xs">
          <span className="text-rose-300">{rightLabel}</span>
          <span className="tabular-nums text-rose-300">{rightValue.toFixed(2)}</span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-black/30">
          <div className="h-full rounded-full bg-rose-400/80" style={{ width: `${rp}%` }} />
        </div>
      </div>
    </div>
  );
}

export function EvidenceList({ items }: { items: string[] }) {
  if (!items.length)
    return <p className="text-sm text-slate-500">유의한 신호 없음.</p>;
  return (
    <ul className="space-y-1.5">
      {items.map((e, i) => (
        <li key={i} className="flex gap-2 text-sm leading-relaxed text-slate-300">
          <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-slate-600" />
          <span>{e}</span>
        </li>
      ))}
    </ul>
  );
}
