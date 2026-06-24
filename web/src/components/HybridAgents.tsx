import type { HybridAgent, HybridReport } from "@/lib/types";
import { EvidenceList, SeverityBadge, Stat } from "./ui";

const AGENT_LABELS: Record<HybridAgent["agent_id"], { title: string; subtitle: string }> = {
  entry_error_psych_hybrid: {
    title: "진입오류 하이브리드",
    subtitle: "기존 진입오류 에이전트 + 리벤지 신호",
  },
  stop_loss_psych_hybrid: {
    title: "손절실패 하이브리드",
    subtitle: "기존 손절실패 에이전트 + 처분효과 신호",
  },
};

function AgentPanel({ agent }: { agent: HybridAgent }) {
  const meta = AGENT_LABELS[agent.agent_id];
  const finding = agent.findings[0];
  const assignment = agent.psych_assignments[0];

  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--panel)] p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {agent.base_agent_id}
          </p>
          <h2 className="mt-1 text-lg font-bold text-slate-100">{meta.title}</h2>
          <p className="mt-1 text-sm text-slate-400">{meta.subtitle}</p>
        </div>
        <SeverityBadge severity={agent.severity} />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-[120px_1fr]">
        <Stat label="Hybrid score" value={agent.score} />
        <div className="rounded-lg border border-[var(--border)] bg-black/20 px-3 py-2.5">
          <div className="text-[11px] uppercase tracking-wide text-slate-500">분배 이유</div>
          <p className="mt-1 text-sm leading-relaxed text-slate-300">{assignment.rationale}</p>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-[var(--border)] bg-black/20 p-4">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <h3 className="font-semibold text-slate-100">{finding.label}</h3>
          <span className="text-xs text-slate-500">{finding.type}</span>
        </div>
        <p className="mb-3 text-sm leading-relaxed text-slate-300">{agent.summary}</p>
        <EvidenceList items={finding.evidence} />
      </div>

      <div className="mt-4">
        <div className="mb-2 text-[11px] uppercase tracking-wide text-slate-500">교정 규칙</div>
        <ul className="space-y-1.5">
          {agent.recommendations.map((item) => (
            <li key={item} className="flex gap-2 text-sm leading-relaxed text-slate-300">
              <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-emerald-400/80" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function HybridAgentsView({ report }: { report: HybridReport }) {
  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-[var(--border)] bg-[var(--panel)] p-5">
        <p className="text-xs font-medium uppercase tracking-widest text-violet-400">
          Hybrid routing
        </p>
        <h2 className="mt-1 text-xl font-bold text-slate-100">
          심리 에이전트를 해체해 두 원인 에이전트에 흡수
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">
          심리 기능 전체를 붙이지 않고, 진입오류와 손절실패에 직접 대응되는 신호만 남겼습니다.
          과매매처럼 해석 범위가 넓은 기능은 하이브리드 에이전트에서 제외합니다.
        </p>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        {report.agents.map((agent) => (
          <AgentPanel key={agent.agent_id} agent={agent} />
        ))}
      </div>

      <section className="rounded-lg border border-[var(--border)] bg-[var(--panel)] p-5">
        <h2 className="text-base font-bold text-slate-100">제외한 심리 기능</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {report.discarded_psych_features.map((feature) => (
            <div key={feature.type} className="rounded-lg border border-[var(--border)] bg-black/20 p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-semibold text-slate-100">{feature.label}</h3>
                <span className="rounded-md bg-slate-500/10 px-2 py-1 text-xs text-slate-400 ring-1 ring-slate-600/30">
                  제외
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{feature.reason}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
