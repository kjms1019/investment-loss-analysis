// why_ui 디자인 공용 상수 + 도메인 아이콘.
import React from "react";
import type { DomainId } from "@/lib/api";

export const DOMAIN: Record<DomainId, {
  name: string; def: string; psych: string; color: string; tint: string; light: string;
}> = {
  entry: { name: "진입오류", def: "이 때부터 잘못 샀다", psych: "리벤지", color: "#F0890C", tint: "#FEF1DF", light: "#FBC988" },
  cut: { name: "손절실패", def: "끊었어야 할 때 못 끊었다", psych: "처분효과", color: "#0B2E59", tint: "#E7ECF4", light: "#9FB1CC" },
};

export const SEV_LABEL: Record<string, string> = { weak: "약함", moderate: "보통", strong: "강함" };

export function DomainIcon({ type, size = 18, color }: { type: DomainId; size?: number; color?: string }) {
  const c = color || DOMAIN[type].color;
  const p = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: c, strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  if (type === "entry")
    return (
      <svg {...p}>
        <circle cx={12} cy={12} r={9} /><circle cx={12} cy={12} r={4} />
        <circle cx={12} cy={12} r={1.4} fill={c} stroke="none" />
      </svg>
    );
  return (
    <svg {...p}>
      <polyline points="3 6 9 12 13 8 21 17" /><polyline points="21 11 21 17 15 17" />
    </svg>
  );
}

export function Logo({ size = 30 }: { size?: number }) {
  return (
    <div style={{ width: size, height: size, borderRadius: size * 0.3, background: "#F5500A", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <svg width={size * 0.57} height={size * 0.57} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
        <polyline points="3 7 9 13 13 9 21 17" /><polyline points="21 12 21 17 16 17" />
      </svg>
    </div>
  );
}

export function Section({ step, label }: { step: string; label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 13.5, color: "#8B95A1", fontWeight: 500 }}>
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#0B2E59" }} />
      {label}
    </div>
  );
}

// 손실 막대 차트 (위=수익, 아래=손실). trades 의 절대 손실 크기로.
export function LossBars({ values, height = 110 }: { values: { v: number; color: string; dim?: boolean }[]; height?: number }) {
  const max = Math.max(1, ...values.map((d) => Math.abs(d.v)));
  return (
    <div style={{ position: "relative", display: "flex", alignItems: "stretch", justifyContent: "space-between", gap: 7, height, width: "100%" }}>
      <div style={{ position: "absolute", top: "50%", left: 0, right: 0, height: 1, background: "#E5E8EB" }} />
      {values.map((d, i) => {
        const hh = Math.min((Math.abs(d.v) / max) * 46, 46);
        const pos = d.v >= 0 ? { bottom: "50%" } : { top: "50%" };
        return (
          <div key={i} style={{ flex: "1 1 0", maxWidth: 22, position: "relative" }}>
            <div style={{ position: "absolute", left: 0, right: 0, ...pos, height: hh + "%", background: d.dim ? "#ECEEF0" : d.color, borderRadius: 2, transition: "all .4s ease" }} />
          </div>
        );
      })}
    </div>
  );
}
