import type { Diagnosis } from "@/lib/types";
import { SEV_META } from "./ui";

export function DiagnosisPanel({ diagnosis }: { diagnosis: Diagnosis }) {
  const isLLM = diagnosis.engine.startsWith("llm:");
  const perType = Object.values(diagnosis.per_type ?? {});

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--panel)] p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-bold text-slate-100">🩺 진단</h2>
        <span
          className={`rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ${
            isLLM
              ? "bg-violet-500/10 text-violet-300 ring-violet-500/30"
              : "bg-slate-500/10 text-slate-400 ring-slate-600/30"
          }`}
        >
          {isLLM ? `LLM · ${diagnosis.engine.replace("llm:", "")}` : "룰 템플릿"}
        </span>
      </div>

      {diagnosis.headline && (
        <p className="mb-4 text-sm leading-relaxed text-slate-200">{diagnosis.headline}</p>
      )}

      {perType.length > 0 ? (
        <div className="space-y-3">
          {perType.map((t, i) => {
            const m = SEV_META[t.severity];
            return (
              <div key={i} className="rounded-xl border border-[var(--border)] bg-black/20 p-3.5">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${m.dot}`} />
                  <span className="font-semibold text-slate-100">{t.label}</span>
                  <span className={`text-xs ${m.text}`}>{m.label}</span>
                </div>
                {t.correction ? (
                  <p className="mt-2 text-sm leading-relaxed text-slate-300">
                    <span className="text-emerald-300">교정 →</span> {t.correction}
                  </p>
                ) : (
                  <p className="mt-2 text-sm text-slate-500">유의한 신호 없음.</p>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <pre className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
          {diagnosis.body}
        </pre>
      )}

      <p className="mt-4 text-[11px] leading-snug text-slate-500">
        ※ 룰/통계 엔진이 계산한 팩트만 사용합니다. 매매 추천이 아니라 사후 복기·행동 교정 가이드입니다.
      </p>
    </div>
  );
}
