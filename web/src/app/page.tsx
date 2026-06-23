"use client";

import { useEffect, useState } from "react";
import { REPORTS, SCENARIO_ORDER } from "@/lib/data";
import { PatternCard } from "@/components/PatternCards";
import { DiagnosisPanel } from "@/components/Diagnosis";
import { Stat } from "@/components/ui";

const won = (n: number) => `${n >= 0 ? "+" : "−"}${Math.abs(n).toLocaleString()}원`;

export default function Home() {
  const [scenario, setScenario] = useState("all");

  // URL 해시(#disposition 등)로 시나리오 딥링크 지원
  useEffect(() => {
    const fromHash = window.location.hash.slice(1);
    if (fromHash && REPORTS[fromHash]) setScenario(fromHash);
  }, []);

  const select = (key: string) => {
    setScenario(key);
    window.history.replaceState(null, "", `#${key}`);
  };

  const report = REPORTS[scenario];
  const s = report.summary;

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:py-12">
      {/* 헤더 */}
      <header className="mb-6">
        <p className="text-xs font-medium uppercase tracking-widest text-violet-400">
          준모 · 심리/과매매 분석 에이전트
        </p>
        <h1 className="mt-1 text-2xl font-bold text-slate-50 sm:text-3xl">
          &ldquo;왜 잃었지?&rdquo; 거래 복기 데모
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">
          완결된 국내주식 거래내역을 사후 복기해 <b className="text-slate-300">리벤지 트레이딩 ·
          과매매 · 처분효과</b> 세 가지 심리 패턴을 진단합니다. 룰/통계 엔진이 팩트를 계산하고
          LLM이 문장만 입히는 하이브리드 구조이며, 아래 수치는 실제 1분봉 가격 기반
          더미 거래내역을 에이전트가 분석한 <b className="text-slate-300">실제 출력</b>입니다.
        </p>
      </header>

      {/* 시나리오 탭 */}
      <div className="mb-5 flex flex-wrap gap-2">
        {SCENARIO_ORDER.map((sc) => {
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

      {/* 요약 */}
      <section className="mb-6 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <Stat label="분석 거래" value={`${s.trade_count}건`} sub={`${s.period_start} ~ ${s.period_end}`} />
        <Stat label="포지션 사이클" value={s.cycle_count} sub={`청산 ${s.closed_cycle_count}`} />
        <Stat
          label="승 / 패"
          value={`${s.win_count} / ${s.loss_count}`}
          tone={s.win_count >= s.loss_count ? "pos" : "neg"}
        />
        <Stat
          label="실현손익"
          value={won(s.total_realized_pnl)}
          tone={s.total_realized_pnl >= 0 ? "pos" : "neg"}
        />
      </section>

      {/* 패턴 카드 */}
      <section className="mb-6 grid gap-4 md:grid-cols-3">
        {report.findings.map((f) => (
          <PatternCard key={f.type} finding={f} />
        ))}
      </section>

      {/* 진단 */}
      <section className="mb-8">
        <DiagnosisPanel diagnosis={report.diagnosis} />
      </section>

      {/* 사이클 테이블 */}
      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-300">
          포지션 사이클 (라운드트립)
        </h2>
        <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-black/30 text-left text-[11px] uppercase tracking-wide text-slate-500">
                <th className="px-3 py-2 font-medium">종목</th>
                <th className="px-3 py-2 font-medium">진입</th>
                <th className="px-3 py-2 text-right font-medium">투입금</th>
                <th className="px-3 py-2 text-right font-medium">보유</th>
                <th className="px-3 py-2 text-right font-medium">수익률</th>
                <th className="px-3 py-2 text-right font-medium">실현손익</th>
              </tr>
            </thead>
            <tbody>
              {report.cycles.map((c, i) => (
                <tr key={i} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2 text-slate-200">
                    {c.name}
                    {!c.closed && (
                      <span className="ml-1.5 rounded bg-sky-500/15 px-1.5 py-0.5 text-[10px] text-sky-300">
                        보유중
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-slate-500">{c.entry_time.slice(0, 16)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-slate-400">
                    {c.invested.toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-slate-400">
                    {c.holding_min == null
                      ? "—"
                      : c.holding_min >= 1440
                        ? `${(c.holding_min / 1440).toFixed(1)}일`
                        : `${Math.round(c.holding_min)}분`}
                  </td>
                  <td
                    className={`px-3 py-2 text-right tabular-nums ${
                      !c.closed ? "text-slate-500" : c.is_win ? "text-emerald-300" : "text-rose-300"
                    }`}
                  >
                    {c.closed ? `${c.return_pct > 0 ? "+" : ""}${c.return_pct}%` : "—"}
                  </td>
                  <td
                    className={`px-3 py-2 text-right tabular-nums ${
                      !c.closed ? "text-slate-500" : c.is_win ? "text-emerald-300" : "text-rose-300"
                    }`}
                  >
                    {c.closed ? won(c.realized_pnl) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <footer className="mt-10 border-t border-[var(--border)] pt-4 text-[11px] text-slate-600">
        멀티에이전트 &ldquo;왜 잃었지?&rdquo; 복기 시스템 · 심리/과매매 에이전트(준모) · 데이터는 실 1분봉 기반 합성 더미
      </footer>
    </main>
  );
}
