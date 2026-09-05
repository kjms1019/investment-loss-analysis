"use client";

// 아키텍처 실시간 트래킹 뷰 (다크 모드, 고대비).
// 데모의 단계/버튼이 바뀌면 archChannel 로 메시지가 와서 해당 노드가 발광(.active)하고
// 나머지는 흐려지며, 노드가 속한 탭으로 자동 전환된다.
//  · 탭 1: 분석단 · 진단 흐름 (세로)
//  · 탭 2: 솔루션단 · 실시간 경고 (세로)
//
// variant
//  · "page" : /architecture 단독 페이지. 발표 때 두 번째 창으로 띄우던 그 화면.
//  · "side" : 데모 화면 우측에 붙는 패널. 심사위원이 창을 두 개 띄울 수는 없으니
//             한 화면에서 앱과 아키텍처가 같이 보이게 한다. 도형이 픽셀 고정폭이라
//             폭을 줄이면 레이아웃이 깨지므로, 비율을 유지한 채 통째로 축소한다.

import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { archSubscribe } from "@/lib/archChannel";

// ── 다크 테마 팔레트 (어두운 배경에서 또렷하게) ──
const BG = "#0C1320";
const PANEL = "#111A29";
const CARD = "#1A2434";
const CARD_BD = "#2D3A52";
const TEXT = "#EAF0F8";       // 노드 제목
const SUB = "#9AAAC2";        // 모노 서브텍스트
const MUTE = "#7787A0";       // 보조
const ARROW = "#93A1B6";      // 화살표·연결선
const ACCENT = "#FF6A2B";     // 강조(활성)
const GLOW = "255,106,43";    // 활성 글로우 rgba 베이스

type Tab = "analysis" | "solution";

export type ArchVariant = "page" | "side";

// side 패널 기준 치수. 내부는 원본 폭 그대로 그리고 transform 으로 줄인다.
const SIDE_INNER_W = 1000;   // 분석단 흐름(920) + 좌우 여백
// 폭이 곧 축소율이다(560/1000 = 0.56). 더 좁히면 노드 글자가 읽히지 않고,
// 더 넓히면 본문 1080 과 나란히 놓을 수 있는 화면이 줄어든다.
export const ARCH_SIDE_W = 560;
const SIDE_SCALE = ARCH_SIDE_W / SIDE_INNER_W;

export default function ArchPanel({ variant = "page" }: { variant?: ArchVariant }) {
  const side = variant === "side";
  const [active, setActive] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("대기 중. 데모에서 단계를 진행하면 여기에 켜집니다");
  const [tab, setTab] = useState<Tab>("analysis");
  const autoTab = useRef(true);

  const A = (id: string) => active.has(id);
  const any = active.size > 0;

  useEffect(() => {
    return archSubscribe((m) => {
      const nodes = Array.isArray(m.nodes) ? m.nodes : [];
      setActive(new Set(nodes));
      if (m.note != null) setNote(m.note || " ");
      if (autoTab.current && nodes.length) {
        if (nodes.some((n) => n.startsWith("s-"))) setTab("solution");
        else if (nodes.some((n) => n.startsWith("a-"))) setTab("analysis");
      }
    });
  }, []);

  const bodyRef = useRef<HTMLDivElement | null>(null);
  const activeKey = useMemo(() => [...active].sort().join(","), [active]);
  useEffect(() => {
    const first = [...active][0];
    const box = bodyRef.current;
    if (!first || !box) return;
    // 패널 자기 안에서만 찾는다. scrollIntoView 는 스크롤 가능한 조상을 전부 움직여서
    // 옆에 붙은 데모 화면까지 같이 끌려간다. 그래서 직접 scrollTop 을 계산한다.
    const el = box.querySelector<HTMLElement>(`[id="${CSS.escape(first)}"]`);
    if (!el) return;
    const top = el.getBoundingClientRect().top - box.getBoundingClientRect().top;
    box.scrollTo({ top: box.scrollTop + top - box.clientHeight / 2, behavior: "smooth" });
  }, [activeKey, tab]);

  return (
    <div style={{
      ...(side
        ? { position: "relative" as const, width: "100%", height: "100%" }
        : { position: "fixed" as const, inset: 0 }),
      background: BG, color: TEXT, fontFamily: "Pretendard, sans-serif",
      display: "flex", flexDirection: "column",
    }}>
      <style>{`
        @keyframes archpulse{0%,100%{box-shadow:0 0 0 4px rgba(${GLOW},.35),0 0 26px 8px rgba(${GLOW},.45)}50%{box-shadow:0 0 0 6px rgba(${GLOW},.7),0 0 52px 18px rgba(${GLOW},.9)}}
        @keyframes archdot{0%,100%{opacity:1}50%{opacity:.25}}
        .arch-node{transition:opacity .25s, transform .25s, box-shadow .25s, outline-color .25s; outline:2px solid transparent; outline-offset:3px; border-radius:9px; position:relative}
        .has-active .arch-node:not(.active){opacity:.5; filter:saturate(.85)}
        .arch-node.active{outline-color:${ACCENT}; transform:scale(1.06); z-index:6; box-shadow:0 0 0 4px rgba(${GLOW},.3),0 0 40px 12px rgba(${GLOW},.65); animation:archpulse 1.15s ease-in-out infinite}
        .arch-scroll::-webkit-scrollbar{width:10px}.arch-scroll::-webkit-scrollbar-thumb{background:#26334a;border-radius:5px}
      `}</style>

      {/* 상단 바 */}
      <div style={{ flexShrink: 0, display: "flex", alignItems: "center", gap: side ? 8 : 14, padding: side ? "9px 12px" : "12px 22px", borderBottom: "1px solid #202D44", background: PANEL, flexWrap: side ? "wrap" : "nowrap" }}>
        <span style={{ fontSize: side ? 11 : 12.5, fontWeight: 800, letterSpacing: 1, color: ACCENT, display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: ACCENT, animation: "archdot 1.4s ease-in-out infinite" }} />LIVE
        </span>
        <span style={{ fontSize: side ? 13 : 15, fontWeight: 700, color: TEXT }}>{side ? "아키텍처 추적" : "소프트웨어 아키텍처 · 실시간 추적"}</span>
        <div style={{ display: "flex", gap: 6, marginLeft: side ? "auto" : 10 }}>
          {([["analysis", side ? "분석단" : "분석단 · 진단"], ["solution", side ? "솔루션단" : "솔루션단 · 실시간"]] as const).map(([id, label]) => (
            <button key={id} onClick={() => { autoTab.current = false; setTab(id); }}
              style={{ cursor: "pointer", fontSize: side ? 11.5 : 13, fontWeight: tab === id ? 700 : 500, borderRadius: 9, padding: side ? "5px 9px" : "7px 14px", border: "1px solid " + (tab === id ? ACCENT : "#2C3A56"), background: tab === id ? "rgba(" + GLOW + ",.16)" : "transparent", color: tab === id ? "#fff" : "#9DB2C9" }}>
              {label}
            </button>
          ))}
        </div>
        <span style={{
          marginLeft: side ? 0 : "auto", fontSize: side ? 12 : 14, fontWeight: 600,
          color: any ? ACCENT : "#8A95A6",
          ...(side
            ? { width: "100%", whiteSpace: "normal" as const, lineHeight: 1.35 }
            : { maxWidth: "44vw", whiteSpace: "nowrap" as const, overflow: "hidden", textOverflow: "ellipsis" }),
        }}>▶ {note}</span>
      </div>

      {/* 본문. side 에서는 도형이 픽셀 고정폭이라 폭을 줄이는 대신 통째로 축소한다. */}
      <div ref={bodyRef} className="arch-scroll" style={{ flex: 1, overflowY: "auto", overflowX: "hidden", padding: side ? "16px 0 60px" : "30px 24px 90px" }}>
        <div style={side ? { width: SIDE_INNER_W, transform: `scale(${SIDE_SCALE})`, transformOrigin: "top left" } : undefined}>
          {tab === "analysis" ? <AnalysisFlow A={A} any={any} /> : <SolutionFlow A={A} any={any} />}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────── 공용 노드 비주얼 ───────────────────────────
function cls(active: boolean) { return "arch-node" + (active ? " active" : ""); }

function Proc({ id, active, title, sub, bar }: { id: string; active: boolean; title: string; sub?: string; bar: string }) {
  return (
    <div id={id} className={cls(active)} style={{ background: active ? "#FFFFFF" : "#EEF2F8", color: "#1A2333", border: `1.5px solid ${active ? bar : "#C9D2E0"}`, borderLeft: `7px solid ${bar}`, borderRadius: 8, padding: "13px 16px", boxShadow: "0 6px 16px rgba(0,0,0,.4)" }}>
      <div style={{ fontSize: 18, fontWeight: 700 }}>{title}</div>
      {sub && <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12.5, color: "#5E6B7C", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function DbCyl({ id, active, title, sub, color, fill }: { id: string; active: boolean; title: string; sub: string; color: string; fill: string }) {
  const f = active ? "#FFFFFF" : fill;
  return (
    <div id={id} className={cls(active)} style={{ width: 300, height: 92, margin: "0 auto" }}>
      <svg width="300" height="92" viewBox="0 0 300 92" style={{ position: "absolute", inset: 0 }}>
        <path d="M2,18 v56 a148,15 0 0 0 296,0 v-56" fill={f} stroke={color} strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
        <ellipse cx="150" cy="18" rx="148" ry="15" fill={f} stroke={color} strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
      </svg>
      <div style={{ position: "absolute", left: 0, right: 0, top: 26, bottom: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 17, fontWeight: 800, color }}>{title}</div>
        <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: "#5E73A8" }}>{sub}</div>
      </div>
    </div>
  );
}

function Diamond({ id, active, title, sub, color }: { id: string; active: boolean; title: string; sub: string; color: string }) {
  return (
    <div id={id} className={cls(active)} style={{ width: 184, height: 138, margin: "0 auto" }}>
      <div style={{ position: "absolute", left: "50%", top: "50%", width: 126, height: 126, transform: "translate(-50%,-50%) rotate(45deg)", background: active ? "#FFFFFF" : "#FBEFD8", border: `2.5px solid ${color}`, borderRadius: 12, boxShadow: "0 6px 16px rgba(0,0,0,.4)" }} />
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "0 14px" }}>
        <div style={{ fontSize: 15, fontWeight: 800, color: "#8A5208", lineHeight: 1.2 }}>{title}</div>
        <div style={{ fontSize: 11, color: "#A8772F", marginTop: 3 }}>{sub}</div>
      </div>
    </div>
  );
}

function SideNote({ id, active, title, sub, color, dashed }: { id?: string; active?: boolean; title: string; sub?: string; color: string; dashed?: boolean }) {
  return (
    <div id={id} className={id ? cls(!!active) : undefined} style={{ background: active ? "#FFFFFF" : "#EEF2F8", color: "#1A2333", border: `1.5px ${dashed ? "dashed" : "solid"} ${color}`, borderRadius: 10, padding: "10px 13px" }}>
      <div style={{ fontSize: 14, fontWeight: 700, color }}>{title}</div>
      {sub && <div style={{ fontSize: 12, color: "#5E6B7C", marginTop: 2, lineHeight: 1.4 }}>{sub}</div>}
    </div>
  );
}

function Gut({ ko, en, active }: { ko: string; en: string; active?: boolean }) {
  return (
    <div style={{ textAlign: "right", paddingRight: 4 }}>
      <div style={{ fontSize: 19, fontWeight: 800, color: active ? ACCENT : "#C7D3E2", transition: "color .2s" }}>{ko}</div>
      <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 1, color: MUTE }}>{en}</div>
    </div>
  );
}

function Down() {
  return (
    <div style={{ display: "flex", justifyContent: "center", padding: "2px 0" }}>
      <svg width="22" height="30"><line x1="11" y1="0" x2="11" y2="21" stroke={ARROW} strokeWidth="2.5" /><path d="M5,19 L11,29 L17,19" fill="none" stroke={ARROW} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
    </div>
  );
}

function Chip({ children, color }: { children: ReactNode; color: string }) {
  return <span style={{ fontSize: 12.5, fontWeight: 700, color, background: color + "22", border: `1.5px solid ${color}66`, borderRadius: 7, padding: "5px 11px" }}>{children}</span>;
}

// ─────────────────────────── 분석단 (세로) ───────────────────────────
function AnalysisFlow({ A, any }: { A: (id: string) => boolean; any: boolean }) {
  const grid: CSSProperties = { display: "grid", gridTemplateColumns: "120px minmax(300px,380px) 320px", columnGap: 22, rowGap: 0, alignItems: "center", justifyContent: "center", maxWidth: 920, margin: "0 auto" };
  const empty = <div />;
  const conn = (<><div />{<Down />}<div /></>);
  return (
    <div className={"arch-flow" + (any ? " has-active" : "")}>
      <SlideHeader eyebrow="ANALYSIS FLOW" title="분석단 · 진단 흐름" suffix="세로 구성" right={"위 → 아래 단방향 흐름 · 과거 거래내역에서 실패 원인 진단"} color="#6E92E8" />
      <div style={{ border: "2px dashed #3D6BE0", background: "rgba(61,107,224,.10)", borderRadius: 18, padding: "20px 26px 26px" }}>
        <div style={{ fontSize: 15, fontWeight: 800, color: "#7FA2F0", marginBottom: 16 }}>분석단 · ANALYSIS <span style={{ fontSize: 12.5, fontWeight: 600, color: "#8FA0C8" }}>Batch · Teacher (전체경로)</span></div>
        <div style={grid}>
          <Gut ko="입력" en="INPUT" active={A("a-input")} />
          <div><Proc id="a-input" active={A("a-input")} title="거래내역 입력" sub="CSV 체결내역" bar="#8C99AE" /></div>
          {empty}
          {conn}
          <Gut ko="총괄·피쳐" en="FEATURE" active={A("a-orch")} />
          <div><Proc id="a-orch" active={A("a-orch")} title="① 총괄·피쳐 추출" sub="orchestrator · 분석용 피쳐 산출" bar="#4D7BE8" /></div>
          {empty}
          {conn}
          <Gut ko="적재" en="DATABASE" active={A("a-db1")} />
          <div><DbCyl id="a-db1" active={A("a-db1")} title="거래 분석 DB" sub="피쳐 적재 · orchestrator.sqlite3" color="#2B57D4" fill="#E6EDFB" /></div>
          {empty}
          {conn}
          <Gut ko="분류" en="CLASSIFY" active={A("a-clf")} />
          <div><Proc id="a-clf" active={A("a-clf")} title="② 분류기  classifier" sub="건별 진입오류·손절실패 분류" bar="#5A78D8" /></div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: MUTE }}>건별 분류 결과</div>
            <div style={{ display: "flex", gap: 7 }}><Chip color="#6E92E8">진입오류</Chip><Chip color="#E0A93E">손절실패</Chip></div>
          </div>
          {conn}
          <Gut ko="라우팅" en="ROUTE" active={A("a-route")} />
          <div><Diamond id="a-route" active={A("a-route")} title="빈도 1위 = 금액 1위?" sub="오류 집계 · 라우팅" color="#D2820F" /></div>
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#3FC4B2" }}>일치 → 즉시 호출</div>
            <SideNote id="a-userpick" active={A("a-userpick")} title="사용자 선택" sub="불일치 시 · 무엇부터 볼지 선택 후 호출" color="#6B4FE0" />
          </div>
          {conn}
          <Gut ko="해석" en="AGENT" active={A("a-agent")} />
          <div><Proc id="a-agent" active={A("a-agent")} title="④ 도메인 에이전트" sub="분류 피쳐 + 심리 피쳐로 해석" bar="#4D7BE8" /></div>
          <div><SideNote id="a-loop" active={A("a-loop")} title="다른 오류도 분석?" sub="예 → 다른 에이전트로 같은 단계 반복" color="#B5650A" dashed /></div>
          {conn}
          <Gut ko="저장" en="FINAL DB" active={A("a-finaldb")} />
          <div><DbCyl id="a-finaldb" active={A("a-finaldb")} title="⑤ 최종 DB" sub="실패원인 저장" color="#0F7B7B" fill="#DFF1EE" /></div>
          {empty}
          {conn}
          <Gut ko="리포트" en="REPORT" active={A("a-report")} />
          <div><Proc id="a-report" active={A("a-report")} title="⑥ 진단 리포트" sub="실패원인 설명 · web 대시보드" bar="#8C99AE" /></div>
          {empty}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────── 솔루션단 (세로) ───────────────────────────
function SolutionFlow({ A, any }: { A: (id: string) => boolean; any: boolean }) {
  const col: CSSProperties = { display: "flex", flexDirection: "column", alignItems: "center", maxWidth: 760, margin: "0 auto" };
  return (
    <div className={"arch-flow" + (any ? " has-active" : "")}>
      <SlideHeader eyebrow="SOLUTION FLOW" title="솔루션단 · 실시간 경고" suffix="세로 구성" right={"위 → 아래 단방향 흐름 · 실시간 추적 · 사전 경고"} color="#E5B96A" />
      <div style={{ border: "2px dashed #D8902A", background: "rgba(216,144,42,.10)", borderRadius: 18, padding: "24px 26px 28px" }}>
        <div style={{ fontSize: 15, fontWeight: 800, color: "#E5B96A", marginBottom: 18 }}>솔루션단 · SOLUTION <span style={{ fontSize: 12.5, fontWeight: 600, color: "#C5A567" }}>Real-time · Student</span></div>
        <div style={col}>
          <div style={{ width: 420 }}><Proc id="s-track" active={A("s-track")} title="실시간 데이터 추적" sub="시세·체결 · 키움 REST" bar="#2BB3B3" /></div>
          <Down />
          <div style={{ width: 420 }}><Proc id="s-feat" active={A("s-feat")} title="피처 계산" sub="진입맥락·포지션 피처 (실시간 · look-ahead 금지)" bar="#3FA9A0" /></div>
          <Down />
          <div style={{ position: "relative", display: "flex", justifyContent: "center", width: "100%" }}>
            <div style={{ position: "absolute", right: "calc(50% + 220px)", top: "50%", transform: "translateY(-50%)", width: 210 }}>
              <SideNote title="분석단 분류기 라벨" sub="→ 예측기 학습 (Label Distillation)" color="#6B4FE0" dashed />
            </div>
            <div style={{ width: 440, display: "flex", flexDirection: "column", gap: 9, alignItems: "center" }}>
              <Proc id="s-pred" active={A("s-pred")} title="단일 예측기  predictor" sub="진입오류·손절실패 동시 예측" bar="#E0A93E" />
              <div style={{ display: "flex", gap: 7 }}><Chip color="#6E92E8">진입오류</Chip><Chip color="#E0A93E">손절실패</Chip><Chip color="#8A95A6">None</Chip></div>
            </div>
          </div>
          <BranchConn />
          <div style={{ display: "flex", gap: 24, justifyContent: "center" }}>
            <div style={{ width: 300 }}><Proc id="s-entry" active={A("s-entry")} title="① 진입오류 경고" sub="신규 진입 직전 · 진입오류 근접 시 알림" bar="#4D7BE8" /></div>
            <div style={{ width: 300 }}><Proc id="s-stop" active={A("s-stop")} title="② 손절 경고" sub="보유 종목 · 시장 급락 · 손절 미실행 시 알림" bar="#E0A93E" /></div>
          </div>
          <MergeConn />
          <div style={{ width: 420 }}><Proc id="s-notify" active={A("s-notify")} title="사용자 알림" sub="대시보드 · 사전 경고 푸시" bar="#9580F0" /></div>
          <div style={{ display: "flex", gap: 22, marginTop: 26, fontSize: 12.5, color: SUB }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><svg width="34" height="10"><line x1="2" y1="5" x2="32" y2="5" stroke="#9580F0" strokeWidth="2.5" strokeDasharray="7 5" /></svg>분석단 → 예측기 (라벨 증류)</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><svg width="34" height="10"><line x1="2" y1="5" x2="32" y2="5" stroke={ARROW} strokeWidth="2.5" /></svg>실시간 처리 흐름</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function BranchConn() {
  return (
    <svg width="624" height="44" style={{ display: "block" }}>
      <g fill="none" stroke={ARROW} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M312,0 V14" />
        <path d="M150,14 H474" />
        <path d="M150,14 V36" /><path d="M144,30 L150,40 L156,30" />
        <path d="M474,14 V36" /><path d="M468,30 L474,40 L480,30" />
      </g>
    </svg>
  );
}

function MergeConn() {
  return (
    <svg width="624" height="44" style={{ display: "block" }}>
      <g fill="none" stroke={ARROW} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M150,0 V18" /><path d="M474,0 V18" />
        <path d="M150,18 H474" />
        <path d="M312,18 V36" /><path d="M306,30 L312,40 L318,30" />
      </g>
    </svg>
  );
}

function SlideHeader({ eyebrow, title, suffix, right, color }: { eyebrow: string; title: string; suffix: string; right: string; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", maxWidth: 920, margin: "0 auto 18px", flexWrap: "wrap", gap: 10 }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: 3, color }}>소프트웨어 아키텍처 · {eyebrow}</div>
        <div style={{ fontSize: 34, fontWeight: 800, marginTop: 6, color: TEXT }}>{title} <span style={{ fontSize: 18, fontWeight: 600, color: MUTE }}>{suffix}</span></div>
      </div>
      <div style={{ fontSize: 13, color: MUTE, textAlign: "right", lineHeight: 1.5 }}>{right}</div>
    </div>
  );
}
