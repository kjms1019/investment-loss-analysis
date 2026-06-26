"use client";

import { useEffect, useState } from "react";
import { REPORTS, SCENARIO_ORDER } from "@/lib/data";
import { FLOWS } from "@/lib/flow";
import { FlowView } from "@/components/FlowView";
import { PatternCard } from "@/components/PatternCards";
import { DiagnosisPanel } from "@/components/Diagnosis";

export default function Home() {
  const [scenario, setScenario] = useState("all");
  const [view, setView] = useState<"flow" | "account">("flow");

  useEffect(() => {
    const fromHash = window.location.hash.slice(1);
    if (fromHash && FLOWS[fromHash]) setScenario(fromHash);
  }, []);

  const select = (key: string) => {
    setScenario(key);
    window.history.replaceState(null, "", `#${key}`);
  };

  const flow = FLOWS[scenario];
  const report = REPORTS[scenario];
  const tabs = SCENARIO_ORDER;

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:py-12">
      <header className="mb-6">
        <p className="text-xs font-medium uppercase tracking-widest text-violet-400">
          준모 · 심리/과매매 분석 에이전트
        </p>
        <h1 className="mt-1 text-2xl font-bold text-slate-50 sm:text-3xl">
          &ldquo;왜 잃었지?&rdquo; 거래 복기 데모
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">
          오케스트레이션이 <b className="text-slate-300">① 시장을 제거한 초과손실(α)로 복기 대상을
          선별</b>하고, <b className="text-slate-300">② 각 손실 거래를 리벤지·과매매·처분효과 중
          하나로 귀속(라우팅)</b>합니다. 아래는 실 1분봉 기반 더미 거래를 파이프라인이 분석한 실제 출력입니다.
        </p>
      </header>

      {/* 시나리오 탭 + 뷰 전환 */}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-2">
          {tabs.map((sc) => {
            const active = sc.key === scenario;
            return (
              <button
                key={sc.key}
                onClick={() => select(sc.key)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
                  active
                    ? "bg-violet-500 text-white"
                    : "border border-[var(--border)] bg-[var(--panel)] text-slate-400 hover:text-slate-200"
                }`}
              >
                {sc.label}
              </button>
            );
          })}
        </div>
        <div className="flex rounded-full border border-[var(--border)] bg-[var(--panel)] p-0.5 text-xs">
          {([["flow", "손실→라우팅"], ["account", "계좌 전체"]] as const).map(([k, label]) => (
            <button
              key={k}
              onClick={() => setView(k)}
              className={`rounded-full px-3 py-1 font-medium transition ${
                view === k ? "bg-slate-700 text-slate-100" : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {view === "flow" ? (
        <FlowView flow={flow} />
      ) : (
        <div className="space-y-6">
          <p className="text-xs text-slate-500">
            참고: 손실 선별과 무관하게 계좌 전체에서 본 심리 경향(룰/통계 + 진단). 큰 그림용.
          </p>
          <section className="grid gap-4 md:grid-cols-3">
            {report.findings.map((f) => (
              <PatternCard key={f.type} finding={f} />
            ))}
          </section>
          <DiagnosisPanel diagnosis={report.diagnosis} />
        </div>
      )}

      <footer className="mt-10 border-t border-[var(--border)] pt-4 text-[11px] text-slate-600">
        멀티에이전트 &ldquo;왜 잃었지?&rdquo; 복기 시스템 · 손실선별(α) → 심리 귀속 · 데이터는 실 1분봉 기반 합성 더미
      </footer>
    </main>
  );
}
