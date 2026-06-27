// why_ui 디자인 공용 상수 + 도메인 아이콘.
import React from "react";
import type { DomainId, TradeChart, AlertChart } from "@/lib/api";

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
export function LossBars({ values, height = 110, minBarPct = 0 }: { values: { v: number; color: string; dim?: boolean }[]; height?: number; minBarPct?: number }) {
  const max = Math.max(1, ...values.map((d) => Math.abs(d.v)));
  return (
    <div style={{ position: "relative", display: "flex", alignItems: "stretch", justifyContent: "flex-start", gap: 8, height, width: "100%" }}>
      <div style={{ position: "absolute", top: "50%", left: 0, right: 0, height: 1, background: "#E5E8EB" }} />
      {values.map((d, i) => {
        // 막대 1개 = 거래 1건. 위험점수 0이어도 거래는 존재하므로 minBarPct 만큼 최소 높이를 보장한다.
        const hh = Math.max(Math.min((Math.abs(d.v) / max) * 46, 46), minBarPct);
        const pos = d.v >= 0 ? { bottom: "50%" } : { top: "50%" };
        return (
          <div key={i} style={{ flex: "0 1 26px", maxWidth: 26, position: "relative" }}>
            <div style={{ position: "absolute", left: 0, right: 0, ...pos, height: hh + "%", background: d.dim ? "#ECEEF0" : d.color, borderRadius: 2, transition: "all .4s ease" }} />
          </div>
        );
      })}
    </div>
  );
}

// ── 거래별 미니차트 ───────────────────────────────────────────────────────────
// 그 거래의 실제 보유구간 가격(종가) 라인 + 피쳐 위치 마커(진입·청산·손절선·돌파·최대낙폭).
const wonK = (n: number) => "₩" + Math.round(n).toLocaleString("ko-KR");
const md = (iso: string) => { const d = new Date(iso); return `${d.getMonth() + 1}/${d.getDate()}`; };

export function TradeMiniChart({ chart, color, tint }: { chart: TradeChart; color: string; tint: string }) {
  const W = 320, H = 188, padL = 8, padR = 62, padT = 18, padB = 26;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const cs = chart.series.map((s) => s.c);
  const n = cs.length;
  if (n < 2) return null;
  const extra = [chart.entry.price, chart.exit.price, ...(chart.stop != null ? [chart.stop] : [])];
  let ymin = Math.min(...cs, ...extra), ymax = Math.max(...cs, ...extra);
  const pad = (ymax - ymin) * 0.1 || 1; ymin -= pad; ymax += pad;
  const X = (i: number) => padL + (i / (n - 1)) * plotW;
  const Y = (p: number) => padT + (1 - (p - ymin) / (ymax - ymin)) * plotH;
  const linePts = cs.map((c, i) => `${X(i).toFixed(1)},${Y(c).toFixed(1)}`).join(" ");
  const areaPts = `${padL},${(padT + plotH).toFixed(1)} ${linePts} ${X(n - 1).toFixed(1)},${(padT + plotH).toFixed(1)}`;
  const ex = chart.entry, xt = chart.exit;
  const lossNeg = (chart.pnl_pct ?? 0) < 0;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block" }} preserveAspectRatio="xMidYMid meet">
      {/* 손절선 (손절실패만) */}
      {chart.stop != null && (
        <g>
          <line x1={padL} x2={padL + plotW} y1={Y(chart.stop)} y2={Y(chart.stop)} stroke="#E2574C" strokeWidth={1} strokeDasharray="4 3" />
          <text x={padL + plotW + 4} y={Y(chart.stop) + 3} fontSize={9} fill="#E2574C">손절선</text>
          <text x={padL + plotW + 4} y={Y(chart.stop) + 14} fontSize={9} fill="#E2574C">{wonK(chart.stop)}</text>
        </g>
      )}
      {/* 가격 라인 + 영역 */}
      <polygon points={areaPts} fill={tint} opacity={0.6} />
      <polyline points={linePts} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" />
      {/* 손절 신호(돌파) 수직선 */}
      {chart.breach && (
        <g>
          <line x1={X(chart.breach.i)} x2={X(chart.breach.i)} y1={padT} y2={padT + plotH} stroke="#E2574C" strokeWidth={1} strokeDasharray="3 3" opacity={0.7} />
          <text x={X(chart.breach.i)} y={padT - 6} fontSize={9} fill="#E2574C" textAnchor="middle" paintOrder="stroke" stroke="#fff" strokeWidth={3} strokeLinejoin="round">손절 신호</text>
        </g>
      )}
      {/* 최대낙폭(저점) */}
      {chart.mae && (
        <circle cx={X(chart.mae.i)} cy={Y(chart.mae.price)} r={2.6} fill="#E2574C" />
      )}
      {/* 진입 마커 (라벨은 흰 외곽선으로 선 위에서도 읽히게) */}
      <circle cx={X(ex.i)} cy={Y(ex.price)} r={4.5} fill={color} stroke="#fff" strokeWidth={1.5} />
      <text x={X(ex.i)} y={Y(ex.price) - 11} fontSize={9.5} fontWeight={700} fill={color} textAnchor="middle" paintOrder="stroke" stroke="#fff" strokeWidth={3.2} strokeLinejoin="round">진입 {wonK(ex.price)}</text>
      {/* 청산 마커 */}
      <circle cx={X(xt.i)} cy={Y(xt.price)} r={4.5} fill="#fff" stroke={color} strokeWidth={2} />
      <text x={X(xt.i)} y={Y(xt.price) + 18} fontSize={9.5} fontWeight={700} fill={lossNeg ? "#E2574C" : color} textAnchor="middle" paintOrder="stroke" stroke="#fff" strokeWidth={3.2} strokeLinejoin="round">청산 {wonK(xt.price)}</text>
      {/* x축 날짜 */}
      <text x={X(ex.i)} y={H - 8} fontSize={8.5} fill="#8B95A1" textAnchor="middle">{md(ex.t)}</text>
      <text x={X(xt.i)} y={H - 8} fontSize={8.5} fill="#8B95A1" textAnchor="middle">{md(xt.t)}</text>
    </svg>
  );
}

// ── 실시간 알림 주식창 차트 ───────────────────────────────────────────────────
// stop : 매수→손절선 돌파→현재가(보유 중 손절실패). entry : 매수 예정 시점.
export function AlertMiniChart({ chart, color }: { chart: AlertChart; color: string }) {
  const W = 320, H = 184, padL = 8, padR = 66, padT = 16, padB = 24;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const cs = chart.series.map((s) => s.c);
  const n = cs.length;
  if (n < 2) return null;
  const extra = [chart.marker.price, ...(chart.stop != null ? [chart.stop] : []), ...(chart.entry ? [chart.entry.price] : [])];
  let ymin = Math.min(...cs, ...extra), ymax = Math.max(...cs, ...extra);
  const pad = (ymax - ymin) * 0.08 || 1; ymin -= pad; ymax += pad;
  const X = (i: number) => padL + (i / (n - 1)) * plotW;
  const Y = (p: number) => padT + (1 - (p - ymin) / (ymax - ymin)) * plotH;
  const line = cs.map((c, i) => `${X(i).toFixed(1)},${Y(c).toFixed(1)}`).join(" ");
  const area = `${padL},${(padT + plotH).toFixed(1)} ${line} ${X(n - 1).toFixed(1)},${(padT + plotH).toFixed(1)}`;
  const mk = chart.marker;
  const isStop = chart.kind === "stop";
  const tint = isStop ? "#E7ECF4" : "#FEF1DF";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block" }} preserveAspectRatio="xMidYMid meet">
      {chart.stop != null && (
        <g>
          <line x1={padL} x2={padL + plotW} y1={Y(chart.stop)} y2={Y(chart.stop)} stroke="#E2574C" strokeWidth={1} strokeDasharray="4 3" />
          <text x={padL + plotW + 4} y={Y(chart.stop) + 3} fontSize={9} fill="#E2574C">손절선</text>
          <text x={padL + plotW + 4} y={Y(chart.stop) + 14} fontSize={9} fill="#E2574C">{wonK(chart.stop)}</text>
        </g>
      )}
      <polygon points={area} fill={tint} opacity={0.6} />
      <polyline points={line} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" />
      {chart.breach && (
        <g>
          <line x1={X(chart.breach.i)} x2={X(chart.breach.i)} y1={padT} y2={padT + plotH} stroke="#E2574C" strokeWidth={1} strokeDasharray="3 3" opacity={0.65} />
          <text x={X(chart.breach.i)} y={padT - 5} fontSize={9} fill="#E2574C" textAnchor="middle" paintOrder="stroke" stroke="#fff" strokeWidth={3} strokeLinejoin="round">손절선 돌파</text>
        </g>
      )}
      {chart.entry && (
        <g>
          <circle cx={X(chart.entry.i)} cy={Y(chart.entry.price)} r={3.6} fill="#fff" stroke={color} strokeWidth={2} />
          <text x={X(chart.entry.i) + 2} y={Y(chart.entry.price) - 8} fontSize={9} fontWeight={600} fill="#8B95A1" textAnchor="start" paintOrder="stroke" stroke="#fff" strokeWidth={3} strokeLinejoin="round">매수 {wonK(chart.entry.price)}</text>
        </g>
      )}
      {/* 현재가(또는 매수 예정점) */}
      <circle cx={X(mk.i)} cy={Y(mk.price)} r={4.6} fill={isStop ? "#E2574C" : color} stroke="#fff" strokeWidth={1.6} />
      <text x={X(mk.i)} y={Y(mk.price) + (isStop ? 16 : -10)} fontSize={9.5} fontWeight={700} fill={isStop ? "#E2574C" : color} textAnchor="end" paintOrder="stroke" stroke="#fff" strokeWidth={3.2} strokeLinejoin="round">{isStop ? "현재" : "매수 예정"} {wonK(mk.price)}</text>
    </svg>
  );
}
