"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import {
  api, type Alert, type AllTrade, type Dashboard, type Trade, type UserItem, type DomainId, type Disposition, type HoldingsResp, type Holding,
} from "@/lib/api";
import { DOMAIN, SEV_LABEL, DomainIcon, Logo, Section, LossBars, TradeMiniChart, AlertMiniChart } from "@/components/why/ui";
import { archSet } from "@/lib/archChannel";
import ArchPanel, { ARCH_SIDE_W } from "@/components/ArchPanel";

const ROUTES = ["intro", "login", "consent", "upload", "analyze", "dashboard", "trades", "profile", "alerts"] as const;
type Screen = (typeof ROUTES)[number];

const NAV_A = [
  { id: "upload", num: "①", label: "업로드" },
  { id: "analyze", num: "②", label: "분석" },
  { id: "dashboard", num: "③", label: "진단" },
  { id: "trades", num: "④", label: "거래별" },
  { id: "profile", num: "⑤", label: "내 성향" },
] as const;
const NAV_B = [{ id: "alerts", num: "⑥", label: "실시간 알림" }] as const;

/** 뷰포트가 기준 폭 이상인지. 아키텍처 패널을 나란히 놓을 자리가 되는지 판단용. */
function useMinWidth(min: number): boolean {
  const [ok, setOk] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(`(min-width:${min}px)`);
    const sync = () => setOk(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, [min]);
  return ok;
}

export default function Home() {
  const [screen, setScreen] = useState<Screen>("intro");
  const [users, setUsers] = useState<UserItem[]>([]);
  const [user, setUser] = useState<string>("");
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [allTrades, setAllTrades] = useState<AllTrade[]>([]);
  const [disp, setDisp] = useState<Disposition | null>(null);
  const [hold, setHold] = useState<HoldingsResp | null>(null);
  const [err, setErr] = useState<string>("");

  const [filterType, setFilterType] = useState<DomainId | "all">("all");
  const [filterSev, setFilterSev] = useState<string>("all");
  const [consentAgreed, setConsentAgreed] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [consentDone, setConsentDone] = useState(false);
  const authedRef = useRef(authed);
  const consentRef = useRef(consentDone);
  authedRef.current = authed;
  consentRef.current = consentDone;
  const [progressStep, setProgressStep] = useState(0);
  const [showResult, setShowResult] = useState(false);
  const analyzedRef = useRef(false); // 4단계 분석을 한 번이라도 끝냈는지 (재진입 시 재시작 방지)
  const [dxDomain, setDxDomain] = useState<DomainId | null>(null); // 분석 완료 화면에서 호출한 진단 도메인
  const [selTrade, setSelTrade] = useState<number | null>(null);
  const [seenDomains, setSeenDomains] = useState<DomainId[]>([]); // 진단~거래별을 거친(=본) 도메인들

  // 해시 라우팅
  useEffect(() => {
    const sync = () => {
      const raw = (window.location.hash || "").replace(/^#\/?/, "");
      // 해시가 없거나 모르는 값이면 서비스 소개로. 링크만 받고 들어온 사람이
      // 맥락 없이 로그인 폼부터 마주치지 않게 한다.
      let id = (ROUTES.includes(raw as Screen) ? raw : "intro") as Screen;
      // 소개·로그인은 누구나 볼 수 있고, 그 뒤로는 동의를 직접 거쳐야 넘어간다
      // (새로고침·URL 직접입력 포함).
      const open = id === "intro" || id === "login";
      if (!open && !authedRef.current) id = "intro";
      else if (!open && id !== "consent" && !consentRef.current) id = "consent";
      if (id !== raw) { window.location.hash = "#/" + id; return; }
      setScreen(id);
    };
    window.addEventListener("hashchange", sync);
    sync();
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  const go = (id: Screen) => { window.location.hash = "#/" + id; };

  // 사용자 목록
  useEffect(() => {
    api.users().then((u) => { setUsers(u); if (u[0]) setUser((p) => p || u[0].id); }).catch((e) => setErr(String(e)));
  }, []);

  // 선택 사용자 데이터 로드
  const loadUser = useCallback((u: string) => {
    if (!u) return;
    setErr("");
    setSeenDomains([]); setDxDomain(null); // 사용자 바뀌면 '본 도메인'·진단 도메인 초기화
    api.dashboard(u).then(setDash).catch((e) => { setDash(null); setErr(String(e)); });
    api.trades(u).then((d) => setTrades(d.trades)).catch(() => setTrades([]));
    api.allTrades(u).then((d) => setAllTrades(d.trades)).catch(() => setAllTrades([]));
    api.disposition(u).then(setDisp).catch(() => setDisp(null));
    api.holdings(u).then(setHold).catch(() => setHold(null));
  }, []);
  useEffect(() => { loadUser(user); }, [user, loadUser]);

  // 분석 진행 애니메이션 — 4단계까지만 자동, 완료 화면으로는 버튼으로 수동 전환.
  // analyzedRef 로 한 번 끝낸 분석은 화면 재진입 시 다시 돌리지 않는다.
  useEffect(() => {
    if (screen !== "analyze") return;
    if (analyzedRef.current) return;
    setProgressStep(0); setShowResult(false);
    const STEP_MS = 2400; // 사람이 단계 문구를 읽고 아키텍처 색인을 따라올 시간 확보
    const ts = [1, 2, 3].map((n) => setTimeout(() => setProgressStep(n), STEP_MS * n));
    ts.push(setTimeout(() => { setProgressStep(4); analyzedRef.current = true; }, STEP_MS * 4));
    return () => ts.forEach(clearTimeout);
  }, [screen]);

  // ── 아키텍처 페이지(/architecture) 실시간 연동: 화면·단계에 맞는 노드를 broadcast ──
  useEffect(() => {
    switch (screen) {
      case "intro":
      case "login":
      case "consent":
        archSet([], "대기 중. 데모를 시작하면 켜집니다"); break;
      case "upload":
        archSet(["a-input"], "① 거래내역 입력 · CSV 업로드"); break;
      case "analyze":
        if (showResult) { archSet(["a-route"], "③ 빈도 1위? or 금액 1위? · 라우팅 판단"); }
        else {
          const m: [string[], string][] = [
            [["a-orch", "a-db1"], "거래내역 파싱 → 분석 DB 적재"],
            [["a-db1"], "손실 선별 (초과수익 α)"],
            // 자동 파이프라인은 '분류기까지만' 색인한다. 라우팅 다이아몬드(a-route)는
            // 사용자가 빈도/금액을 '선택'하는 순간에만 깜빡이고, 도메인 에이전트(a-agent)는
            // 선택을 마친 뒤에만 켜진다.
            [["a-clf"], "2-way 분류: 건별 진입오류·손절실패"],
            [["a-clf"], "건별 분류 결과 정리"],
          ];
          const [nodes, note] = m[Math.min(progressStep, 3)];
          archSet(nodes, note);
        }
        break;
      case "dashboard":
        archSet(["a-agent"], "④ 도메인 에이전트 · 도메인별 진단"); break;
      case "trades":
        archSet(["a-agent"], "④ 거래별 설명 · 도메인 에이전트"); break;
      case "profile":
        archSet(["a-finaldb", "a-report"], "⑤ 최종 DB → ⑥ 진단 리포트 (성향)"); break;
      case "alerts":
        archSet(["s-track", "s-feat", "s-pred"], "솔루션단 · 실시간 예측 추적"); break;
    }
  }, [screen, progressStep, showResult]);

  const showNav = !(screen === "intro" || screen === "login" || screen === "consent");
  const curUserName = users.find((u) => u.id === user)?.name || "";

  // 아키텍처 패널: 발표 때는 창을 두 개 띄워 옆에 놓았지만 심사위원은 그럴 수 없다.
  // 그래서 같은 화면 우측에 붙인다. 로그인·동의 화면에서는 보여줄 게 없어 접어둔다.
  //
  // 넓은 화면에서는 본문에 패널 폭만큼 오른쪽 여백을 줘서 화면이 통째로 왼쪽으로
  // 밀려나게 한다(본문 자체의 폭·비율은 건드리지 않는다). 화면이 좁으면 여백을
  // 주는 순간 본문이 찌그러지므로, 그때는 패널을 위에 겹쳐 띄운다.
  const [archOpen, setArchOpen] = useState(true);
  const roomy = useMinWidth(1680);  // 본문 1080 + 패널 560 + 여백
  const showArch = archOpen && showNav;
  const archInline = showArch && roomy;

  return (
    <div style={{ minHeight: "100vh", background: "#fff", color: "#191F28", paddingRight: archInline ? ARCH_SIDE_W : 0, transition: "padding-right .18s ease" }}>
      {showNav && (
        <header style={{ position: "sticky", top: 0, zIndex: 20, background: "rgba(255,255,255,.9)", backdropFilter: "blur(10px)", borderBottom: "1px solid #F2F4F6" }}>
          <div style={{ maxWidth: 1080, margin: "0 auto", padding: "12px clamp(16px,4vw,40px)", display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <Logo /><div style={{ fontWeight: 700, fontSize: 16 }}>왜 잃었지?</div>
            </div>
            <nav style={{ display: "flex", alignItems: "center", gap: 5, flexWrap: "wrap", marginLeft: "auto" }}>
              {[...NAV_A, null, ...NAV_B].map((n, i) =>
                n === null ? (
                  <div key={i} style={{ width: 1, height: 20, background: "#E5E8EB", margin: "0 4px" }} />
                ) : (
                  <NavBtn key={n.id} active={screen === n.id} num={n.num} label={n.label} onClick={() => go(n.id as Screen)} />
                )
              )}
              {/* 사용자 선택은 ① 업로드 단계에서만 — 현재 대상만 표시 */}
              {curUserName && (
                <span style={{ marginLeft: 8, display: "inline-flex", alignItems: "center", gap: 6, background: "#F2F4F6", borderRadius: 9, padding: "7px 11px", fontSize: 13, color: "#4E5968" }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#F5500A" }} />{curUserName}
                </span>
              )}
              <button
                onClick={() => setArchOpen((v) => !v)}
                title="에이전트 아키텍처를 화면 오른쪽에서 실시간으로 따라갑니다"
                style={{ marginLeft: 8, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, borderRadius: 9, padding: "7px 11px", fontSize: 13, fontWeight: 600, border: "1px solid " + (archOpen ? "#0B2E59" : "#E5E8EB"), background: archOpen ? "#0B2E59" : "#fff", color: archOpen ? "#fff" : "#4E5968" }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: archOpen ? "#FF6A2B" : "#B0B8C1" }} />
                아키텍처
              </button>
            </nav>
          </div>
        </header>
      )}

      <main style={{ maxWidth: 1080, margin: "0 auto", padding: "28px clamp(16px,4vw,40px) 96px" }}>
        {err && <div style={{ background: "#FFF3EC", color: "#F5500A", border: "1px solid #FBD9BF", borderRadius: 12, padding: "12px 14px", marginBottom: 18, fontSize: 14 }}>
          백엔드 연결 오류: {err}. <b>uvicorn analysis.api.main:app --port 8000</b> 실행 중인지 확인하세요.
        </div>}

        {screen === "intro" && <Intro onStart={() => go("login")} />}
        {screen === "login" && <Login onLogin={() => { setAuthed(true); go("consent"); }} onDemo={() => { if (users[0]) setUser(users[0].id); setAuthed(true); go("consent"); }} onBack={() => go("intro")} />}
        {screen === "consent" && <Consent agreed={consentAgreed} toggle={() => setConsentAgreed((v) => !v)} onBack={() => go("login")} onStart={() => { setConsentDone(true); go("upload"); }} />}
        {screen === "upload" && <Upload users={users} user={user} setUser={setUser} onStart={() => { analyzedRef.current = false; setProgressStep(0); setShowResult(false); go("analyze"); }} />}
        {screen === "analyze" && <Analyze step={progressStep} done={showResult} trades={trades} all={allTrades} onSeeResult={() => setShowResult(true)} onGo={(d) => { setDxDomain(d); go("dashboard"); }} />}
        {screen === "dashboard" && <DashboardView dash={dash} all={allTrades} focus={dxDomain} onCard={(t) => { setFilterType(t); setFilterSev("all"); go("trades"); }} />}
        {screen === "trades" && (() => {
          const cur: DomainId = dxDomain ?? (dash?.dominant.id as DomainId) ?? "cut";
          const other: DomainId = cur === "cut" ? "entry" : "cut";
          const otherCount = dash?.counts[other] ?? 0;
          const markSeen = () => setSeenDomains((s) => (s.includes(cur) ? s : [...s, cur]));
          return <TradesView
            trades={trades} filterType={filterType} setFilterType={setFilterType}
            filterSev={filterSev} setFilterSev={setFilterSev} selTrade={selTrade} setSelTrade={setSelTrade}
            other={{ id: other, name: DOMAIN[other].name, count: otherCount, seen: seenDomains.includes(other) }}
            onSeeOther={() => { markSeen(); setDxDomain(other); setFilterType(other); setFilterSev("all"); setSelTrade(0); go("dashboard"); }}
            onToProfile={() => { markSeen(); go("profile"); }}
          />;
        })()}
        {screen === "profile" && <ProfileView disp={disp} userName={curUserName} />}
        {screen === "alerts" && <AlertsView data={hold} />}
      </main>

      {showArch && (
        <aside
          aria-label="에이전트 아키텍처 실시간 추적"
          style={{
            position: "fixed", top: 0, right: 0, bottom: 0, width: ARCH_SIDE_W,
            zIndex: 30, borderLeft: "1px solid #202D44",
            // 나란히 놓일 때는 본문 옆에 붙은 한 덩어리로 보이게 그림자를 뺀다.
            // 겹쳐 뜰 때만 위에 떠 있다는 걸 그림자로 알린다.
            boxShadow: archInline ? "none" : "-18px 0 44px rgba(11,46,89,.22)",
          }}>
          <ArchPanel variant="side" />
        </aside>
      )}
    </div>
  );
}

function NavBtn({ active, num, label, onClick }: { active: boolean; num: string; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{ display: "flex", alignItems: "center", gap: 7, borderRadius: 10, padding: "8px 13px 8px 10px", fontSize: 14, cursor: "pointer", fontWeight: active ? 600 : 500, border: "none", background: active ? "rgba(245,80,10,.10)" : "transparent", color: active ? "#F5500A" : "#8B95A1" }}>
      <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 18, height: 18, borderRadius: "50%", fontSize: 12, fontWeight: 600, background: active ? "#F5500A" : "#F2F4F6", color: active ? "#fff" : "#8B95A1" }}>{num}</span>
      <span>{label}</span>
    </button>
  );
}

// ── INTRO (첫 화면) ──────────────────────────────────────────────────────────
// 발표 자리에서는 PPT로 맥락을 다 깔고 이 서비스를 열었다. 심사위원은 URL 만 받고
// 들어오므로 그 맥락이 통째로 비어 있다. 그래서 로그인 앞에 소개를 세우되,
// 긴 스크롤 대신 좌우로 넘기는 덱으로 만든다. 발표 슬라이드와 같은 호흡이라
// 한 화면에 하나의 이야기만 놓이고, 읽는 사람이 속도를 쥔다.
//
// 화면 문법(전 슬라이드 공통)
//   · 얇은 머리말(kicker) → 큰 제목 → 본문 → 시각물 순서로 시선을 흘린다.
//   · 배경에 흐린 큰 숫자를 깔아 지금 몇 번째 이야기인지 눈으로 잡히게 한다.
//   · 채워진 카드를 남발하지 않고 헤어라인과 여백으로 구획한다.
//   · 강조색은 슬라이드마다 딱 한 군데. α 슬라이드 하나만 어둡게 눌러 리듬을 준다.

const INK = "#10192B";        // 제목
const NAVY = "#0B2E59";
const ACCENT = "#F5500A";
const MUTED = "#7A8699";      // 보조 텍스트
const HAIR = "#E8ECF1";       // 헤어라인
const BODY = "#56616F";

const kicker: CSSProperties = { fontSize: 11, fontWeight: 700, letterSpacing: 1.6, color: MUTED };
const slideTitle: CSSProperties = { fontSize: "clamp(21px,2.9vw,27px)", fontWeight: 700, color: INK, lineHeight: 1.38, letterSpacing: -0.5, margin: "10px 0 0" };
const slideBody: CSSProperties = { fontSize: 14.5, color: BODY, lineHeight: 1.78, margin: "14px 0 0" };

/** 손실 경로 두 유형의 모양. 분류기가 군집으로 나눈 두 축을 단순화해 그린다. */
const LOSS_SHAPES = {
  entry: {
    label: "진입오류", quote: "살 때부터 잘못 샀다", color: "#B5650A",
    desc: "고점 추격, 과열 종목 추격 진입. 매수 당일부터 손실이 쌓입니다.",
    axis: "손실이 초반에 몰립니다",
    path: [82, 74, 55, 40, 33, 30, 34, 31, 28, 32, 30, 27, 31, 29, 30],
    stop: null as number | null,
  },
  cut: {
    label: "손절실패", quote: "끊어야 할 때 못 끊었다", color: NAVY,
    desc: "손절선을 이탈했는데 버티거나, 물타기로 손실을 키웁니다.",
    axis: "최저점이 뒤에 옵니다",
    path: [82, 86, 90, 84, 88, 80, 72, 66, 58, 47, 38, 30, 24, 18, 15],
    stop: 62,
  },
};

function ShapeChart({ pts, color, stop }: { pts: number[]; color: string; stop: number | null }) {
  const W = 320, H = 132, padX = 4, padY = 12;
  const X = (i: number) => padX + (i / (pts.length - 1)) * (W - padX * 2);
  const Y = (v: number) => padY + (1 - v / 100) * (H - padY * 2);
  const line = pts.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block" }}>
      <polygon points={`${padX},${H - padY} ${line} ${W - padX},${H - padY}`} fill={color} opacity={0.07} />
      {stop != null && (
        <>
          <line x1={padX} x2={W - padX} y1={Y(stop)} y2={Y(stop)} stroke="#E2574C" strokeWidth={1} strokeDasharray="3 3" />
          <text x={W - padX} y={Y(stop) - 5} fontSize={9} fill="#E2574C" textAnchor="end" letterSpacing={0.3}>손절선</text>
        </>
      )}
      <polyline points={line} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={X(0)} cy={Y(pts[0])} r={3.2} fill="#fff" stroke={color} strokeWidth={1.8} />
      <text x={X(0) + 6} y={Y(pts[0]) - 7} fontSize={9.5} fill={MUTED}>매수</text>
    </svg>
  );
}

/** 배경에 깔리는 흐린 숫자. 지금 몇 번째 이야기인지 눈으로 잡히게 한다. */
function GhostNum({ n }: { n: string }) {
  return (
    <div aria-hidden style={{
      position: "absolute", right: -6, top: -30, fontSize: 150, fontWeight: 800,
      color: "#F2F5F9", lineHeight: 1, letterSpacing: -6, pointerEvents: "none", userSelect: "none",
    }}>{n}</div>
  );
}

function Chevron({ dir }: { dir: "l" | "r" }) {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"
      style={{ transform: dir === "l" ? "rotate(180deg)" : undefined }}>
      <path d="M9 5l7 7-7 7" />
    </svg>
  );
}

function Intro({ onStart }: { onStart: () => void }) {
  const [i, setI] = useState(0);
  const [dom, setDom] = useState<"entry" | "cut">("entry");
  const [mine, setMine] = useState(-8);
  const [market, setMarket] = useState(-7);
  // 끝까지 본 뒤에는 계속 켜져 있게 둔다. 되돌아갔다고 다시 꺼지면 갇힌 느낌이 난다.
  const [unlocked, setUnlocked] = useState(false);

  const LIVE = "#F5500A";   // 실시간단
  const ANAL = NAVY;        // 분석단

  const SLIDES = useMemo(() => ([
    { stage: "cover" as const, kicker: "WHY WE LOSE", num: "" },
    { stage: "analysis" as const, kicker: "분석단 · 무엇을 보는가", num: "" },
    { stage: "analysis" as const, kicker: "분석단 · STEP 01 포집", num: "01" },
    { stage: "analysis" as const, kicker: "분석단 · STEP 02 진단", num: "02" },
    { stage: "live" as const, kicker: "분석단 → 실시간단 · STEP 03 저장", num: "03" },
    { stage: "live" as const, kicker: "실시간단 · STEP 04 경고", num: "04" },
  ]), []);
  const LAST = SLIDES.length - 1;

  const move = useCallback((d: number) => setI((v) => Math.min(SLIDES.length - 1, Math.max(0, v + d))), [SLIDES.length]);
  useEffect(() => { if (i === LAST) setUnlocked(true); }, [i, LAST]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") move(1);
      else if (e.key === "ArrowLeft") move(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move]);

  const shape = LOSS_SHAPES[dom];
  const alpha = +(mine - market).toFixed(1);
  const isMine = alpha <= -2;
  const cols: CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: 30, alignItems: "center" };

  const bodies: ReactNode[] = [
    // 00 표지
    (
      <div style={{ maxWidth: 600 }}>
        <h1 style={{ fontSize: "clamp(25px,3.6vw,34px)", fontWeight: 700, color: INK, lineHeight: 1.32, letterSpacing: -0.9, margin: "10px 0 0" }}>
          사람마다<br /><span style={{ color: ACCENT }}>잃는 습관</span>이 따로 있습니다.
        </h1>
        <p style={{ ...slideBody, margin: "18px 0 0", maxWidth: 520 }}>
          누구는 늘 고점에서 따라 사고, 누구는 늘 손절선을 넘기고도 버팁니다.
          지난 거래에서 그 습관을 찾아내고, 다음 거래에서 같은 습관이 또 나오려는 순간에 잡아줍니다.
        </p>
        <div style={{ display: "flex", gap: 26, marginTop: 26, paddingTop: 18, borderTop: `1px solid ${HAIR}`, flexWrap: "wrap" }}>
          {[["분석단", "지난 거래에서 내 습관을 찾는다", ANAL], ["실시간단", "다음 거래에서 그 습관을 잡는다", LIVE]].map(([t, d, c]) => (
            <div key={t as string} style={{ minWidth: 190 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: c as string, letterSpacing: 0.4 }}>{t}</div>
              <div style={{ fontSize: 13, color: BODY, marginTop: 5, lineHeight: 1.6 }}>{d}</div>
            </div>
          ))}
        </div>
      </div>
    ),
    // 01 분석단 — 무엇을 보는가
    (
      <div>
        <h2 style={slideTitle}>종목을 분석하지 않습니다. 사람을 분석합니다.</h2>
        <div style={{ ...cols, marginTop: 24, gap: 0 }}>
          <div style={{ paddingRight: 24 }}>
            <div style={{ ...kicker, color: "#B6BFCB" }}>이런 분석이 아닙니다</div>
            <div style={{ fontSize: 17, fontWeight: 700, color: "#98A2B0", margin: "10px 0", letterSpacing: -0.4 }}>&ldquo;이 종목이 왜 떨어졌나&rdquo;</div>
            <div style={{ fontSize: 13, color: "#98A2B0", lineHeight: 1.72 }}>
              섹터 분석, 시황, 거시 환경. 이미 많은 곳이 해주는 이야기이고, 시장 수익률을 빼는 순간 사라지는 설명입니다.
            </div>
          </div>
          <div style={{ paddingLeft: 24, borderLeft: `1px solid ${HAIR}` }}>
            <div style={{ ...kicker, color: ACCENT }}>우리가 답하는 질문</div>
            <div style={{ fontSize: 17, fontWeight: 700, color: INK, margin: "10px 0", letterSpacing: -0.4 }}>&ldquo;나는 왜 매번 여기서 잃나&rdquo;</div>
            <div style={{ fontSize: 13, color: BODY, lineHeight: 1.72 }}>
              시장 탓을 걷어낸 자리에 남는 건 오직 내가 내린 선택입니다. 그 선택이 반복되면 습관이고, 습관은 바꿀 수 있습니다.
            </div>
          </div>
        </div>
      </div>
    ),
    // 02 포집 (α)
    (
      <div>
        <h2 style={slideTitle}>시장 요인이 아닌 &lsquo;내가&rsquo; 못한 순간을 포집합니다.</h2>
        <p style={{ ...slideBody, margin: "10px 0 0", maxWidth: 540 }}>종목·섹터·거시 요인은 이 단계에서 통째로 빠집니다. 값을 직접 움직여 보세요.</p>
        <div style={{ background: NAVY, borderRadius: 14, padding: "18px 20px", color: "#fff", marginTop: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#A9BDD6", marginBottom: 14, letterSpacing: -0.1 }}>
            초과손실 α = 절대손익 − 같은 기간 KOSPI 수익률
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(210px,1fr))", gap: 22, alignItems: "center" }}>
            <div>
              {([["내 손익", mine, setMine], ["같은 기간 KOSPI", market, setMarket]] as const).map(([label, val, set]) => (
                <div key={label} style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#A9BDD6", marginBottom: 5 }}>
                    <span>{label}</span>
                    <b style={{ color: "#fff", fontSize: 13.5, fontVariantNumeric: "tabular-nums" }}>{val > 0 ? "+" : ""}{val}%</b>
                  </div>
                  <input type="range" min={-30} max={10} step={1} value={val}
                    onChange={(e) => set(Number(e.target.value))} style={{ width: "100%", accentColor: ACCENT, cursor: "pointer" }} />
                </div>
              ))}
            </div>
            <div style={{ borderLeft: "1px solid rgba(255,255,255,.12)", paddingLeft: 20 }}>
              <div style={{ fontSize: 11, color: "#8FA6C4", letterSpacing: 0.6, marginBottom: 4 }}>내 탓인 손실</div>
              <div style={{ fontSize: 29, fontWeight: 700, letterSpacing: -1.1, fontVariantNumeric: "tabular-nums", color: isMine ? "#FF9A66" : "#7FE3C4" }}>
                {alpha > 0 ? "+" : ""}{alpha}%
              </div>
              <div style={{ fontSize: 12, color: "#A9BDD6", marginTop: 7, lineHeight: 1.6 }}>
                {isMine ? "내 습관을 볼 차례입니다. 복기 대상." : "시장이 빠진 날입니다. 복기 대상에서 제외."}
              </div>
            </div>
          </div>
        </div>
        <div style={{ fontSize: 12, color: MUTED, marginTop: 10, lineHeight: 1.65 }}>
          -8%를 잃었어도 그날 시장이 -7% 빠졌다면 내 몫은 -1%뿐입니다.
        </div>
      </div>
    ),
    // 03 진단 (도메인)
    (
      <div>
        <h2 style={slideTitle}>그 순간, 무엇을 잘못했는지 가립니다.</h2>
        <div style={{ display: "flex", gap: 6, margin: "16px 0 20px" }}>
          {(["entry", "cut"] as const).map((k) => {
            const on = dom === k;
            return (
              <button key={k} onClick={() => setDom(k)}
                style={{ cursor: "pointer", fontSize: 12.5, fontWeight: on ? 700 : 500, borderRadius: 8, padding: "7px 14px",
                  border: `1px solid ${on ? INK : HAIR}`, background: on ? INK : "#fff", color: on ? "#fff" : MUTED, letterSpacing: -0.2 }}>
                {LOSS_SHAPES[k].label}
              </button>
            );
          })}
        </div>
        <div style={cols}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: INK, letterSpacing: -0.5, marginBottom: 9 }}>&ldquo;{shape.quote}&rdquo;</div>
            <div style={{ fontSize: 13, color: BODY, lineHeight: 1.75, marginBottom: 12 }}>{shape.desc}</div>
            <div style={{ fontSize: 11.5, color: shape.color, fontWeight: 600, paddingTop: 11, borderTop: `1px solid ${HAIR}` }}>
              손실 경로 특징 · {shape.axis}
            </div>
          </div>
          <div>
            <ShapeChart pts={shape.path} color={shape.color} stop={shape.stop} />
            <div style={{ fontSize: 10.5, color: "#A6B0BD", textAlign: "center", marginTop: 2 }}>보유 기간 중 가격 경로 (개념도)</div>
          </div>
        </div>
        <div style={{ fontSize: 12, color: MUTED, marginTop: 16, lineHeight: 1.65 }}>
          리벤지 매매·처분효과 같은 심리 신호는 별도 유형이 아니라, 이 두 가지를 설명하는 보강 근거로 씁니다.
        </div>
      </div>
    ),
    // 04 저장 — 분석단이 실시간단으로 넘어가는 지점
    (
      <div>
        <h2 style={slideTitle}>여기까지가 분석단입니다. 찾아낸 습관은 개인 프로필에 저장됩니다.</h2>
        <p style={{ ...slideBody, margin: "10px 0 0", maxWidth: 560 }}>
          한 번 진단하고 끝나면 다음 달에 똑같이 반복합니다. 그래서 결과를 리포트로 흘려보내지 않고, 사용자 개인 프로필에 습관으로 남깁니다.
        </p>
        {/* 분석단 → 프로필 → 실시간단 */}
        <div style={{ display: "flex", alignItems: "stretch", gap: 0, marginTop: 20, flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 200px", padding: "14px 18px 14px 0" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: ANAL, letterSpacing: 0.6, marginBottom: 8 }}>분석단</div>
            <div style={{ fontSize: 13.5, color: BODY, lineHeight: 1.65 }}>지난 1년치 거래에서 시장 탓을 걷어내고, 실패의 모양을 가려냅니다.</div>
          </div>
          <div style={{ flex: "1 1 230px", padding: "14px 18px", borderLeft: `1px solid ${HAIR}`, borderRight: `1px solid ${HAIR}`, background: "#FAFBFC" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: ACCENT, letterSpacing: 0.6, marginBottom: 8 }}>내 습관 프로필</div>
            <div style={{ fontSize: 14.5, fontWeight: 700, color: INK, letterSpacing: -0.3, marginBottom: 5 }}>손절선 이탈 후 2일 이상 보유</div>
            <div style={{ fontSize: 12.5, color: BODY, lineHeight: 1.6 }}>
              다른 사람보다 <b style={{ color: ACCENT, fontWeight: 700 }}>1.4배</b> 자주 반복 · 처분효과
            </div>
          </div>
          <div style={{ flex: "1 1 200px", padding: "14px 0 14px 18px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: LIVE, letterSpacing: 0.6, marginBottom: 8 }}>실시간단</div>
            <div style={{ fontSize: 13.5, color: BODY, lineHeight: 1.65 }}>이 프로필이 다음 거래를 지켜보는 기준이 됩니다. 사람마다 다른 기준입니다.</div>
          </div>
        </div>
        <div style={{ fontSize: 12, color: MUTED, marginTop: 16, lineHeight: 1.65 }}>
          같은 -5% 하락이어도, 손절을 미루는 사람과 고점을 쫓는 사람에게 필요한 경고는 다릅니다.
        </div>
      </div>
    ),
    // 05 실시간 경고
    (
      <div>
        <h2 style={slideTitle}>다음 거래에서, 그 습관이 또 나오려는 순간 알립니다.</h2>
        <p style={{ ...slideBody, margin: "10px 0 0", maxWidth: 560 }}>
          시세와 보유 종목을 계속 지켜보다가, 내 습관이 재현되려는 두 지점에서 개입합니다.
        </p>
        <div style={{ ...cols, marginTop: 18, gap: 24 }}>
          <div>
            {[
              ["매수 버튼을 누르기 직전", "늘 고점에서 따라 사던 그 모양이면 주문 전에 알립니다"],
              ["보유 종목이 손절선에 닿을 때", "넘기고 버티던 습관이 또 나오려는 순간에 알립니다"],
            ].map(([t, d], k) => (
              <div key={t} style={{ paddingTop: k === 0 ? 0 : 12, marginTop: k === 0 ? 0 : 10, borderTop: k === 0 ? "none" : `1px solid ${HAIR}` }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: INK, letterSpacing: -0.3 }}>{t}</div>
                <div style={{ fontSize: 12.5, color: MUTED, marginTop: 4, lineHeight: 1.6 }}>{d}</div>
              </div>
            ))}
          </div>
          {/* 경고 카드 축소본 */}
          <div style={{ border: `1px solid ${HAIR}`, borderLeft: `3px solid ${LIVE}`, borderRadius: 10, padding: "13px 15px", background: "#fff" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 3 }}>
              <div style={{ fontSize: 13.5, fontWeight: 700, color: INK }}>기업은행</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: LIVE, fontVariantNumeric: "tabular-nums" }}>-7.3%</div>
            </div>
            <div style={{ fontSize: 11, color: MUTED, marginBottom: 10, fontVariantNumeric: "tabular-nums" }}>손절선 ₩20,758 · 현재 ₩20,250</div>
            <div style={{ fontSize: 12.5, color: BODY, lineHeight: 1.6, marginBottom: 10 }}>
              손절선 아래로 내려왔어요. 더 버티지 말고 지금 손절선을 지키세요.
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <div style={{ flex: 1, height: 4, borderRadius: 2, background: "#EEF1F5", overflow: "hidden" }}>
                <div style={{ width: "88%", height: "100%", background: LIVE }} />
              </div>
              <span style={{ fontSize: 11, fontWeight: 700, color: LIVE, fontVariantNumeric: "tabular-nums" }}>위험도 88</span>
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 20, paddingTop: 14, borderTop: `1px solid ${HAIR}` }}>
          {[["798종목", "KOSPI 1분봉 5,467만 행"], ["AUC 0.839", "5-fold 교차검증"], ["심리 3패턴", "논문 실측값에 맞춤"]].map(([t, d]) => (
            <div key={t}>
              <div style={{ fontSize: 13.5, fontWeight: 700, color: INK, letterSpacing: -0.3, fontVariantNumeric: "tabular-nums" }}>{t}</div>
              <div style={{ fontSize: 11, color: MUTED, marginTop: 2 }}>{d}</div>
            </div>
          ))}
        </div>
      </div>
    ),
  ];

  const cur = SLIDES[i];
  const stageColor = cur.stage === "live" ? LIVE : cur.stage === "analysis" ? ANAL : MUTED;
  const arrow = (enabled: boolean): CSSProperties => ({
    width: 32, height: 32, borderRadius: "50%", display: "inline-flex", alignItems: "center", justifyContent: "center",
    border: `1px solid ${enabled ? "#D5DCE5" : HAIR}`, background: "#fff",
    color: enabled ? INK : "#CBD3DC", cursor: enabled ? "pointer" : "default", padding: 0,
  });

  return (
    <div style={{ maxWidth: 780, margin: "0 auto", padding: "4px 2px 22px" }}>
      {/* 머리: 로고 + 단계별 진행 표시 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 12, borderBottom: `1px solid ${HAIR}`, gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Logo size={24} />
          <div style={{ fontWeight: 700, fontSize: 14.5, color: INK, letterSpacing: -0.3 }}>왜 잃었지?</div>
          <div style={{ fontSize: 11, color: MUTED, paddingLeft: 9, marginLeft: 3, borderLeft: `1px solid ${HAIR}` }}>초개인화 주식 거래 습관 교정</div>
        </div>
        {/* 분석단·실시간단이 눈으로 갈라져 보이게 묶어서 표시한다 */}
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {([["분석단", "analysis", ANAL], ["실시간단", "live", LIVE]] as const).map(([label, st, c]) => (
            <div key={st} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.5, color: cur.stage === st ? c : "#C2CAD4" }}>{label}</span>
              <div style={{ display: "flex", gap: 4 }}>
                {SLIDES.map((sl, k) => sl.stage !== st ? null : (
                  <button key={k} onClick={() => setI(k)} aria-label={`${k + 1}번째`}
                    style={{ width: k === i ? 16 : 6, height: 3, borderRadius: 2, border: "none", padding: 0,
                      background: k === i ? c : "#DFE5EC", cursor: "pointer", transition: "width .22s, background .22s" }} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 무대 */}
      <div style={{ position: "relative", overflow: "hidden", minHeight: 372, padding: "22px 0 6px" }}>
        <GhostNum n={cur.num} />
        <div key={i} style={{ position: "relative", animation: "introIn .32s cubic-bezier(.22,.8,.28,1) both" }}>
          <div style={{ ...kicker, color: stageColor }}>{cur.kicker}</div>
          {bodies[i]}
        </div>
        <style>{`@keyframes introIn{from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:none}}`}</style>
      </div>

      {/* 발: 좌우 이동 + 항상 자리를 지키는 CTA */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 12, borderTop: `1px solid ${HAIR}`, gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button onClick={() => move(-1)} disabled={i === 0} aria-label="이전" style={arrow(i > 0)}><Chevron dir="l" /></button>
          <button onClick={() => move(1)} disabled={i === LAST} aria-label="다음" style={arrow(i < LAST)}><Chevron dir="r" /></button>
          <span style={{ fontSize: 11, color: MUTED, letterSpacing: 1.2, fontVariantNumeric: "tabular-nums" }}>
            {String(i + 1).padStart(2, "0")} <span style={{ color: "#CBD3DC" }}>/ {String(SLIDES.length).padStart(2, "0")}</span>
          </span>
        </div>
        {/* 끝까지 보면 불이 들어온다. 그 전까지는 자리만 지킨다. */}
        <button onClick={() => unlocked && onStart()} disabled={!unlocked}
          title={unlocked ? "" : "마지막 장까지 보면 활성화됩니다"}
          style={{
            border: "none", borderRadius: 10, padding: "12px 26px", fontSize: 14, fontWeight: 600, letterSpacing: -0.2,
            background: unlocked ? ACCENT : "#EEF1F5", color: unlocked ? "#fff" : "#AEB7C2",
            cursor: unlocked ? "pointer" : "default",
            boxShadow: unlocked ? "0 4px 14px rgba(245,80,10,.28)" : "none",
            transition: "background .35s ease, color .35s ease, box-shadow .35s ease",
          }}>
          서비스 이용하기
        </button>
      </div>
    </div>
  );
}

// ── LOGIN ────────────────────────────────────────────────────────────────────
function Login({ onLogin, onDemo, onBack }: { onLogin: () => void; onDemo: () => void; onBack: () => void }) {
  const [phone, setPhone] = useState("");
  const [pw, setPw] = useState("");
  const ready = phone.trim().length > 0 && pw.length > 0;
  return (
    <div style={{ maxWidth: 400, margin: "0 auto", padding: "48px 2px 40px" }}>
      <button onClick={onBack} style={{ background: "none", border: "none", padding: "6px 6px 6px 0", cursor: "pointer", fontSize: 13.5, color: "#8B95A1", marginBottom: 10 }}>← 서비스 소개로</button>
      <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 40 }}><Logo size={34} /><div style={{ fontWeight: 700, fontSize: 18 }}>왜 잃었지?</div></div>
      <h1 style={{ fontSize: 26, fontWeight: 700, color: "#0B2E59", lineHeight: 1.34, margin: "0 0 10px" }}>내 거래 복기를<br />이어서 확인해 볼까요?</h1>
      <p style={{ color: "#8B95A1", fontSize: 16, lineHeight: 1.6, margin: "0 0 32px" }}>로그인하면 지난 진단 결과와 실시간 알림을 그대로 이어볼 수 있어요.</p>
      <label style={lbl}>휴대폰 번호</label>
      <input placeholder="010-0000-0000" value={phone} onChange={(e) => setPhone(e.target.value)} style={inp} />
      <label style={{ ...lbl, marginTop: 16 }}>비밀번호</label>
      <input type="password" placeholder="비밀번호 입력" value={pw} onChange={(e) => setPw(e.target.value)} style={inp} />
      <button onClick={() => ready && onLogin()} disabled={!ready} style={{ ...primaryBtn, marginTop: 24, background: ready ? "#F5500A" : "#E5E8EB", color: ready ? "#fff" : "#B0B8C1", cursor: ready ? "pointer" : "default" }}>로그인</button>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, marginTop: 18, fontSize: 14.5, color: "#8B95A1" }}>
        <span style={{ cursor: "pointer" }}>회원가입</span><span style={{ color: "#E5E8EB" }}>|</span><span style={{ cursor: "pointer" }}>비밀번호 찾기</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "30px 0 18px" }}><div style={{ flex: 1, height: 1, background: "#F2F4F6" }} /><span style={{ fontSize: 13.5, color: "#B0B8C1" }}>또는</span><div style={{ flex: 1, height: 1, background: "#F2F4F6" }} /></div>
      <button onClick={onDemo} style={{ width: "100%", background: "#F2F4F6", color: "#4E5968", border: "none", borderRadius: 14, padding: 16, fontSize: 15.5, fontWeight: 600, cursor: "pointer" }}>체험 계정으로 둘러보기</button>
    </div>
  );
}

// ── CONSENT ──────────────────────────────────────────────────────────────────
const CONSENT_ITEMS = ["개인정보 수집·이용", "계좌 및 거래정보 수집·이용", "실시간 보유종목 모니터링", "자동화된 위험 분석 및 알림", "투자 유의사항 확인"];
function Consent({ agreed, toggle, onBack, onStart }: { agreed: boolean; toggle: () => void; onBack: () => void; onStart: () => void }) {
  return (
    <div style={{ maxWidth: 440, margin: "0 auto", padding: "8px 2px 40px" }}>
      <button onClick={onBack} style={{ background: "none", border: "none", padding: "6px 6px 6px 0", cursor: "pointer", marginBottom: 8 }}>
        <svg width={24} height={24} viewBox="0 0 24 24" fill="none" stroke="#191F28" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
      </button>
      <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0B2E59", lineHeight: 1.36, margin: "6px 0 12px" }}>반복 실수를<br />실시간으로 짚어드릴게요</h1>
      <p style={{ color: "#8B95A1", fontSize: 16, lineHeight: 1.6, margin: "0 0 22px" }}>정확한 진단을 위해 최근 1년간의 거래·보유 종목 내역을 불러올게요.</p>
      <div style={{ background: "#0B2E59", borderRadius: 16, padding: 20, display: "flex", alignItems: "center", marginBottom: 26 }}>
        <div style={{ flex: 1 }}><div style={{ fontSize: 14.5, color: "#9DB2C9", marginBottom: 7 }}>분석 대상</div><div style={{ fontSize: 19, fontWeight: 700, color: "#fff" }}>최근 1년</div></div>
        <div style={{ width: 1, alignSelf: "stretch", background: "rgba(255,255,255,.16)", margin: "0 18px" }} />
        <div style={{ flex: 1 }}><div style={{ fontSize: 14.5, color: "#9DB2C9", marginBottom: 7 }}>연동 증권사</div><div style={{ fontSize: 19, fontWeight: 700, color: "#fff" }}>4곳 지원</div></div>
      </div>
      {CONSENT_ITEMS.map((ci) => (
        <div key={ci} style={{ display: "flex", alignItems: "center", gap: 11, padding: "13px 0", borderBottom: "1px solid #F2F4F6" }}>
          <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke={agreed ? "#F5500A" : "#C4CDD5"} strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#0B2E59" }}>필수</span>
          <span style={{ fontSize: 15.5, color: "#333D4B", flex: 1 }}>{ci}</span>
        </div>
      ))}
      <div onClick={toggle} style={{ display: "flex", alignItems: "center", gap: 11, padding: "15px 16px", background: "#F2F4F6", borderRadius: 14, cursor: "pointer", margin: "20px 0 14px" }}>
        <div style={{ width: 24, height: 24, borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center", background: agreed ? "#F5500A" : "#fff", border: "1px solid " + (agreed ? "#F5500A" : "#D1D6DB") }}>
          <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
        </div>
        <span style={{ fontSize: 16, fontWeight: 600 }}>필수 동의 항목을 모두 확인하고 동의합니다.</span>
      </div>
      <button onClick={() => agreed && onStart()} disabled={!agreed} style={{ width: "100%", border: "none", borderRadius: 14, padding: 16, fontSize: 16, fontWeight: 600, cursor: agreed ? "pointer" : "default", background: agreed ? "#F5500A" : "#E5E8EB", color: agreed ? "#fff" : "#B0B8C1" }}>동의하고 시작하기</button>
    </div>
  );
}

// ── ① UPLOAD ─────────────────────────────────────────────────────────────────
function Upload({ users, user, setUser, onStart }: { users: UserItem[]; user: string; setUser: (u: string) => void; onStart: () => void }) {
  const curName = users.find((u) => u.id === user)?.name || "";
  return (
    <div style={{ maxWidth: 620, margin: "8px auto 0" }}>
      <Section step="1" label="복기 루프 · 1단계 업로드" />
      <h1 style={{ fontSize: "clamp(25px,4.4vw,33px)", fontWeight: 700, lineHeight: 1.32, color: "#0B2E59", margin: "14px 0 12px" }}>수익률이 아니라,<br />당신만의 <span style={{ color: "#F5500A" }}>반복 실수</span>를 찾아드려요.</h1>
      <p style={{ color: "#8B95A1", fontSize: 16, lineHeight: 1.65, margin: "0 0 26px" }}>1년치 거래내역을 올리면, 시장 탓 손실은 걷어내고 <b style={{ color: "#191F28", fontWeight: 600 }}>‘당신 탓’ 손실만</b> 골라 그 원인을 짚어드려요.</p>

      <label style={lbl}>분석 대상 <span style={{ color: "#B0B8C1", fontWeight: 400 }}>· 예시 데이터셋 {users.length}명 중 선택</span></label>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(120px,1fr))", gap: 8, marginBottom: 4 }}>
        {users.length === 0 && <div style={{ fontSize: 13.5, color: "#B0B8C1", padding: "10px 2px" }}>사용자 목록을 불러오는 중…</div>}
        {users.map((u) => {
          const sel = u.id === user;
          return (
            <button key={u.id} onClick={() => setUser(u.id)} style={{ cursor: "pointer", textAlign: "left", borderRadius: 11, padding: "11px 13px", fontSize: 14, fontWeight: sel ? 700 : 500, background: sel ? "rgba(245,80,10,.10)" : "#F2F4F6", color: sel ? "#F5500A" : "#4E5968", border: "1.5px solid " + (sel ? "#F5500A" : "transparent") }}>
              <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: sel ? "#F5500A" : "#C4CDD5" }} />{u.name}
              </div>
            </button>
          );
        })}
      </div>

      <label style={{ ...lbl, marginTop: 18 }}>증권사</label>
      <select style={{ ...inp, cursor: "pointer" }}>{["미래에셋증권", "키움증권", "삼성증권", "NH투자증권", "한국투자증권"].map((b) => <option key={b}>{b}</option>)}</select>
      <label style={{ ...lbl, marginTop: 18 }}>거래내역 파일 (CSV)</label>
      <div style={{ border: "1.5px dashed #D1D6DB", borderRadius: 14, padding: "30px 20px", textAlign: "center", background: "#F8F9FA" }}>
        <svg width={30} height={30} viewBox="0 0 24 24" fill="none" stroke="#0B2E59" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: 10 }}><path d="M12 16V4" /><polyline points="7 9 12 4 17 9" /><path d="M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" /></svg>
        <div style={{ fontSize: 15.5, color: "#191F28", fontWeight: 500 }}>여기로 CSV를 끌어다 놓거나 클릭해 업로드</div>
        <div style={{ fontSize: 13.5, color: "#8B95A1", marginTop: 6 }}>미래에셋·키움·삼성·NH 등 거래내역 내보내기 파일 지원</div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "14px 0 22px", fontSize: 13.5, color: "#8B95A1" }}>지금은 예시 거래 데이터로 체험하는 중이에요. {curName && <b style={{ color: "#191F28", fontWeight: 600 }}>· 분석 대상: {curName}</b>}</div>
      <button onClick={() => user && onStart()} disabled={!user} style={{ ...primaryBtn, background: user ? "#F5500A" : "#E5E8EB", color: user ? "#fff" : "#B0B8C1", cursor: user ? "pointer" : "default" }}>{user ? "내 거래 복기 시작하기" : "분석 대상을 선택해 주세요"}</button>
    </div>
  );
}

// ── ② ANALYZE ────────────────────────────────────────────────────────────────
const PIPELINE = [
  { label: "거래내역 파싱", desc: "체결 내역을 매수·매도 사이클로 묶고 있어요." },
  { label: "손실 선별 (초과수익 α)", desc: "시장 영향을 제거하고 ‘진짜 당신 탓 손실’만 골라내는 중…" },
  { label: "2-way 라우팅 (진입오류·손절실패)", desc: "각 손실을 두 도메인으로 나누고, 심리 신호를 붙이는 중…" },
  { label: "거래별 설명 생성", desc: "거래마다 왜 잃었는지 한 단락씩 정리하는 중…" },
];
function Analyze({ step, done, trades, all, onSeeResult, onGo }: {
  step: number; done: boolean; trades: Trade[]; all: AllTrade[]; onSeeResult: () => void; onGo: (d: DomainId) => void;
}) {
  const stepsDone = step >= PIPELINE.length; // 4단계 모두 완료
  // 선택은 도메인이 아니라 '카드(축)' 단위 — 두 카드가 같은 도메인일 수 있어서.
  const [pick, setPick] = useState<"freq" | "amount" | null>(null);
  const [calling, setCalling] = useState(false); // 선택 후 '분석 에이전트 호출' 카드 표시
  useEffect(() => { if (!done) { setPick(null); setCalling(false); } }, [done]);
  // 아키텍처 연동: 완료 화면의 선택/호출 단계
  useEffect(() => {
    if (!done) return;
    if (calling) archSet(["a-agent"], "④ 도메인 에이전트 호출");
    else if (pick) archSet(["a-route", "a-userpick"], "사용자 선택 · 무엇부터 볼지");
    else archSet(["a-route"], "③ 빈도 1위? or 금액 1위? · 라우팅 판단");
  }, [done, pick, calling]);

  // 전체 거래 차트 — 단계가 진행될수록 '색인'이 점진적으로 들어간다.
  //  step≤1(파싱): 전체 거래 무색  → step2(손실 선별): 본인 탓 손실만 진하게  → step≥3(라우팅): 도메인 색.
  // all = 이익 포함 전체 거래(백엔드 /api/all-trades). type=null 이면 이익·비선별 거래(항상 회색).
  // 이익·손실 높이는 각 방향 최대값으로 따로 정규화 → 큰 이익에 손실이 묻히지 않게.
  const stage = step <= 1 ? "all" : step === 2 ? "loss" : "routed";
  const lossCount = all.filter((t) => t.type != null).length;
  const maxPos = Math.max(1, ...all.filter((t) => t.pnl > 0).map((t) => t.pnl));
  const maxNeg = Math.max(1, ...all.filter((t) => t.pnl < 0).map((t) => -t.pnl));
  const chartBars = all.map((t) => {
    const v = t.pnl >= 0 ? t.pnl / maxPos : -(-t.pnl / maxNeg); // 이익 위(+), 손실 아래(-)
    if (stage === "all") return { v, color: "#C4CDD5", dim: true };       // 처음엔 전부 회색
    if (!t.type) return { v, color: "#ECEEF0", dim: true };               // 이익·비선별 → 끝까지 회색
    if (stage === "loss") return { v, color: "#9FB1CC", dim: false };     // 선별된 손실만 색
    return { v, color: DOMAIN[t.type].color, dim: false };                // 라우팅 도메인 색
  });
  const stageNote = stage === "all" ? "전체 거래를 불러왔어요" : stage === "loss" ? `‘당신 탓’ 손실 ${lossCount}건을 골라내는 중…` : "진입오류·손절실패로 분류하는 중…";
  // 카드·축선·헤더는 처음부터 존재한다. 거래내역 파싱 전(step 0)에는 막대만 비우고(레이아웃 안 밀림),
  // 파싱이 끝나면(step≥1) 막대가 그 자리에 채워진다.
  const chart = chartBars.length > 0 ? (
    <div style={{ background: "#F8F9FA", border: "1px solid #F2F4F6", borderRadius: 16, padding: "18px 18px 16px", marginBottom: 22 }}>
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
        <div style={{ fontSize: 14.5, fontWeight: 600 }}>최근 거래 {chartBars.length}건<span style={{ color: "#8B95A1", fontWeight: 400, fontSize: 13, marginLeft: 8 }}>막대 1개 = 거래 1건 · {stageNote}</span></div>
        <div style={{ display: "flex", gap: 12, marginLeft: "auto", fontSize: 12, color: "#8B95A1" }}>
          <Legend color="#ECEEF0" label="전체(이익)" /><Legend color={DOMAIN.entry.color} label="진입오류" /><Legend color={DOMAIN.cut.color} label="손절실패" />
        </div>
      </div>
      <LossBars values={step >= 1 ? chartBars : []} height={100} />
    </div>
  ) : null;

  if (!done) {
    return (
      <div style={{ maxWidth: 780, margin: "8px auto 0" }}>
        <Section step="2" label="복기 루프 · 2단계 분석 진행" />
        <h2 style={{ fontSize: "clamp(22px,3.6vw,28px)", fontWeight: 700, color: "#0B2E59", margin: "14px 0 10px" }}>당신의 거래를 천천히 읽고 있어요</h2>
        <p style={{ color: "#8B95A1", fontSize: 16, margin: "0 0 22px" }}>시장 영향을 제거하고 <b style={{ color: "#191F28" }}>‘진짜 당신 탓 손실’</b>만 골라내는 중이에요.</p>
        {chart}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {PIPELINE.map((p, i) => {
            const st = i < step ? "done" : i === step ? "active" : "pending";
            return (
              <div key={i} style={{ display: "flex", gap: 13, alignItems: "flex-start", padding: 16, borderRadius: 14, background: st === "active" ? "#FFF3EC" : "#F2F4F6", border: "1px solid " + (st === "active" ? "rgba(245,80,10,.28)" : "transparent") }}>
                <div style={{ width: 24, height: 24, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {st === "done" ? <svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="#F5500A" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5" /></svg>
                    : st === "active" ? <div style={{ width: 18, height: 18, borderRadius: "50%", border: "2px solid #E5E8EB", borderTopColor: "#F5500A", animation: "wlspin .8s linear infinite" }} />
                      : <div style={{ width: 11, height: 11, borderRadius: "50%", border: "2px solid #D1D6DB" }} />}
                </div>
                <div>
                  <div style={{ fontSize: 14.5, fontWeight: 600, color: st === "pending" ? "#B0B8C1" : "#191F28" }}>{p.label}</div>
                  <div style={{ fontSize: 12.5, lineHeight: 1.55, marginTop: 3, color: st === "active" ? "#F5500A" : "#8B95A1" }}>{p.desc}</div>
                </div>
              </div>
            );
          })}
        </div>
        <button onClick={() => stepsDone && onSeeResult()} disabled={!stepsDone}
          style={{ ...primaryBtn, marginTop: 22, background: stepsDone ? "#F5500A" : "#E5E8EB", color: stepsDone ? "#fff" : "#B0B8C1", cursor: stepsDone ? "pointer" : "default" }}>
          {stepsDone ? "분석 결과 보기 →" : "분석 중이에요…"}
        </button>
      </div>
    );
  }
  // 완료 화면 = 2카드. 빈도+총손실금을 손실 거래에서 직접 집계(백엔드 의존 X).
  const w = statsFromTrades(trades);
  const opts = w
    ? ([
        { axis: "freq" as const, head: "가장 자주 반복된 문제", primary: "빈도", type: w.freq },
        { axis: "amount" as const, head: "손실 금액이 가장 컸던 문제", primary: "총손실금", type: w.amount },
      ])
    : [];
  const selType = w ? (pick === "freq" ? w.freq : pick === "amount" ? w.amount : null) : null;

  return (
    <div style={{ maxWidth: 780, margin: "8px auto 0" }}>
      <Section step="2" label="복기 루프 · 분석 완료" />
      <h2 style={{ fontSize: "clamp(22px,3.6vw,28px)", fontWeight: 700, color: "#0B2E59", margin: "14px 0 12px" }}>분석이 완료됐어요</h2>
      <p style={{ color: "#4E5968", fontSize: 16, lineHeight: 1.8, margin: "0 0 22px" }}>가장 <b style={{ color: "#191F28" }}>자주 반복된</b> 문제와 한 번에 <b style={{ color: "#191F28" }}>잃은 금액이 컸던</b> 문제예요. 어느 쪽부터 바로잡을지 <b style={{ color: "#191F28" }}>하나만</b> 골라주세요.</p>

      {!w && <Loading />}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 13 }}>
        {opts.map((o) => {
          const m = DOMAIN[o.type]; const st = w!.stats[o.type]; const sel = pick === o.axis;
          return (
            <button key={o.axis} onClick={() => setPick(o.axis)} style={{ textAlign: "left", cursor: "pointer", background: sel ? m.tint : "#fff", borderTop: "3px solid " + m.color, borderRight: "1.5px solid " + (sel ? m.color : "#E5E8EB"), borderBottom: "1.5px solid " + (sel ? m.color : "#E5E8EB"), borderLeft: "1.5px solid " + (sel ? m.color : "#E5E8EB"), borderRadius: 14, padding: 18 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: 11.5, fontWeight: 600, color: m.color, background: m.tint, borderRadius: 6, padding: "4px 9px" }}>{o.head}</span>
                {sel && <div style={{ width: 24, height: 24, borderRadius: "50%", background: m.color, display: "flex", alignItems: "center", justifyContent: "center" }}><svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></div>}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 9, marginTop: 13 }}>
                <div style={{ width: 36, height: 36, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", background: m.tint }}><DomainIcon type={o.type} size={19} /></div>
                <div style={{ fontSize: 17, fontWeight: 700 }}>{m.name}</div>
              </div>
              <div style={{ display: "flex", gap: 16, marginTop: 14 }}>
                <div>
                  <div style={{ fontSize: 12, color: o.primary === "빈도" ? m.color : "#B0B8C1", marginBottom: 3, fontWeight: o.primary === "빈도" ? 600 : 400 }}>빈도</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: o.primary === "빈도" ? m.color : "#B0B8C1" }}>{st.count}<span style={{ fontSize: 12.5, color: o.primary === "빈도" ? m.color : "#B0B8C1", fontWeight: 500, marginLeft: 2 }}>건</span></div>
                </div>
                <div style={{ width: 1, background: "#E5E8EB" }} />
                <div>
                  <div style={{ fontSize: 12, color: o.primary === "총손실금" ? m.color : "#B0B8C1", marginBottom: 3, fontWeight: o.primary === "총손실금" ? 600 : 400 }}>총 손실금</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: o.primary === "총손실금" ? m.color : "#B0B8C1" }}>{won(st.amount)}</div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <button onClick={() => { if (selType) { const d = selType; setCalling(true); setTimeout(() => onGo(d), 1900); } }} disabled={!selType || calling}
        style={{ ...primaryBtn, marginTop: 22, background: selType ? "#F5500A" : "#E5E8EB", color: selType ? "#fff" : "#B0B8C1", cursor: selType && !calling ? "pointer" : "default" }}>
        {selType ? `‘${DOMAIN[selType].name}’ 진단 결과 보기 →` : "둘 중 하나를 선택해 주세요"}
      </button>

      {calling && selType && (
        <div style={{ position: "fixed", inset: 0, zIndex: 50, background: "rgba(11,46,89,.45)", backdropFilter: "blur(3px)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div style={{ background: "#fff", borderRadius: 20, padding: "34px 30px", width: "min(420px,100%)", textAlign: "center", boxShadow: "0 20px 60px rgba(11,46,89,.28)" }}>
            <div style={{ width: 48, height: 48, margin: "0 auto 20px", borderRadius: "50%", border: "3px solid #E5E8EB", borderTopColor: DOMAIN[selType].color, animation: "wlspin .8s linear infinite" }} />
            <div style={{ display: "inline-flex", alignItems: "center", gap: 9, marginBottom: 12 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", background: DOMAIN[selType].tint }}><DomainIcon type={selType} size={19} /></div>
              <span style={{ fontSize: 18, fontWeight: 700, color: DOMAIN[selType].color }}>{DOMAIN[selType].name}</span>
            </div>
            <div style={{ fontSize: 17, fontWeight: 700, color: "#191F28" }}>분석 에이전트를 호출합니다</div>
            <div style={{ fontSize: 13.5, color: "#8B95A1", marginTop: 8 }}>선택한 문제를 깊게 진단하고 있어요…</div>
          </div>
        </div>
      )}
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{ width: 9, height: 9, borderRadius: 2, background: color }} />{label}
    </span>
  );
}

// ── ③ DASHBOARD ──────────────────────────────────────────────────────────────
// 선택한 도메인별 '문제 양상 + 원인' 설명 — 그래프만으로 안 읽히는 부분을 말로 풀어준다.
const DX_TEXT: Record<DomainId, { pattern: string; cause: string }> = {
  cut: {
    pattern: "끊었어야 할 지점을 지나치고 버티다 손실을 키운 거래가 반복됐어요.",
    cause: "손실을 확정하는 고통을 피하려 ‘곧 회복되겠지’ 하며 미루는 처분효과가 작동했어요. 손절선을 정해두지 않았거나, 정해두고도 지키지 못한 경우가 많아요.",
  },
  entry: {
    pattern: "근거가 무르익기 전에 들어가, 진입 시점부터 불리했던 거래가 반복됐어요.",
    cause: "직전 손실을 빨리 만회하려는 리벤지 심리나 놓칠라(FOMO)가 작동했어요. 매수 전 점검 없이 충동적으로 들어간 경우가 많아요.",
  },
};
function DashboardView({ dash, all, focus, onCard }: { dash: Dashboard | null; all: AllTrade[]; focus: DomainId | null; onCard: (t: DomainId) => void }) {
  if (!dash) return <Loading />;
  const fd: DomainId = focus ?? dash.dominant.id; // 호출한 진단 도메인 (없으면 1순위)
  const m = DOMAIN[fd];
  const od: DomainId = fd === "cut" ? "entry" : "cut";
  // 분석탭과 동일한 전체거래 손익 차트(이익 위·손실 아래)를 그대로 쓰되, 분석 중인 도메인만 색칠한다.
  const maxPos = Math.max(1, ...all.filter((t) => t.pnl > 0).map((t) => t.pnl));
  const maxNeg = Math.max(1, ...all.filter((t) => t.pnl < 0).map((t) => -t.pnl));
  const focusBars = all.map((t) => {
    const v = t.pnl >= 0 ? t.pnl / maxPos : -(-t.pnl / maxNeg);
    return t.type === fd
      ? { v, color: m.color, dim: false }   // 분석 중인 도메인 → 색
      : { v, color: "#ECEEF0", dim: true };  // 이익·다른 도메인 → 회색
  });
  const fc = dash.counts[fd];
  const total = dash.total_loss_trades || (dash.counts.cut + dash.counts.entry);
  const pct = total > 0 ? Math.round((fc / total) * 100) : 0;
  const dx = DX_TEXT[fd];
  return (
    <div>
      <Section step="3" label="복기 루프 · 3단계 진단 대시보드" />
      <h2 style={{ fontSize: "clamp(24px,4.2vw,36px)", fontWeight: 700, color: "#0B2E59", lineHeight: 1.3, margin: "14px 0 12px" }}>이번에 짚어볼 문제는<br /><span style={{ color: m.color, background: m.tint, padding: "0 10px", borderRadius: 10 }}>{m.name}</span>입니다.</h2>
      <p style={{ color: "#8B95A1", fontSize: 16, lineHeight: 1.65, margin: "0 0 26px", whiteSpace: "nowrap" }}>본인 탓 손실 <b style={{ color: "#191F28" }}>{total}건</b> 중 <b style={{ color: m.color }}>{m.name} {fc}건</b>을 깊게 들여다봤어요. 괜찮아요, 뭐가 문제였을까요?</p>

      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "stretch", gap: 13, marginBottom: 18 }}>
        <div style={{ flex: "1 1 300px", display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: 13 }}>
          <Stat label="본인 탓 손실 거래" value={`${total}`} unit="건" />
          <Stat label="손절실패" value={`${dash.counts.cut}`} unit="건" />
          <Stat label="진입오류" value={`${dash.counts.entry}`} unit="건" />
        </div>

        {focusBars.length > 0 && (
          <div style={{ flex: "1 1 360px", background: "#F8F9FA", border: "1px solid #F2F4F6", borderRadius: 16, padding: "18px 18px 16px", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
              <DomainIcon type={fd} size={18} />
              <div style={{ fontSize: 14.5, fontWeight: 600 }}>전체 거래 {focusBars.length}건<span style={{ color: "#8B95A1", fontWeight: 400, fontSize: 13, marginLeft: 8 }}>막대 1개 = 거래 1건 · 위 이익 · 아래 손실</span></div>
              <div style={{ display: "flex", gap: 12, marginLeft: "auto", fontSize: 12, color: "#8B95A1" }}>
                <Legend color={m.color} label={`${m.name} ${fc}건`} /><Legend color="#ECEEF0" label="그 외 거래" />
              </div>
            </div>
            <LossBars values={focusBars} height={100} />
          </div>
        )}
      </div>

      <div style={{ background: m.tint, borderRadius: 16, padding: "20px 20px 22px", marginBottom: 18 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 13 }}>
          <div style={{ width: 34, height: 34, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", background: "#fff" }}><DomainIcon type={fd} size={18} /></div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#191F28" }}>이런 양상이에요</div>
        </div>
        <p style={{ fontSize: 15, lineHeight: 1.75, color: "#333D4B", margin: "0 0 14px" }}>
          전체 손실 <b style={{ color: "#191F28" }}>{total}건</b> 가운데 <b style={{ color: m.color }}>{m.name}가 {fc}건({pct}%)</b>, {DOMAIN[od].name}가 {dash.counts[od]}건이에요. {dx.pattern}
        </p>
        <div style={{ background: "#fff", borderRadius: 12, padding: "14px 15px" }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: m.color, marginBottom: 6 }}>왜 이런 일이 반복될까요</div>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: "#4E5968", margin: 0 }}>{dx.cause}</p>
        </div>
      </div>

      <button onClick={() => onCard(fd)} style={{ ...primaryBtn, background: "#fff", color: m.color, border: "1.5px solid " + m.color, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
        거래별로 더 자세히 분석해볼까요? →
      </button>
    </div>
  );
}

// ── ④ TRADES ─────────────────────────────────────────────────────────────────
const SIG_W: Record<string, number> = { 확대: 0.35, 지연: 0.3, 물타기: 0.2 };
function TradesView({ trades, filterType, setFilterType, filterSev, setFilterSev, selTrade, setSelTrade, other, onSeeOther, onToProfile }: {
  trades: Trade[]; filterType: DomainId | "all"; setFilterType: (t: DomainId | "all") => void;
  filterSev: string; setFilterSev: (s: string) => void; selTrade: number | null; setSelTrade: (n: number | null) => void;
  other: { id: DomainId; name: string; count: number; seen: boolean }; onSeeOther: () => void; onToProfile: () => void;
}) {
  const [asking, setAsking] = useState(false);
  const shouldAsk = other.count > 0 && !other.seen; // 안 본 다른 도메인이 거래가 있으면 물어본다
  // 아키텍처 연동: '다른 오류도 분석?' 반복 프롬프트가 뜨면 루프 노드를 함께 점등
  useEffect(() => {
    if (asking) archSet(["a-loop"], "다른 오류도 분석? · 반복 여부 묻기");
    else archSet(["a-agent"], "④ 거래별 설명 · 도메인 에이전트");
  }, [asking]);
  const filtered = trades.filter((t) => (filterType === "all" || t.type === filterType) && (filterSev === "all" || t.sev === filterSev));
  const active = selTrade != null && selTrade < filtered.length ? selTrade : 0;
  const t = filtered[active];
  const m = t ? DOMAIN[t.type] : DOMAIN.cut;
  const eW = Math.round((t?.eScore ?? 0) * 100), cW = Math.round((t?.cScore ?? 0) * 100);
  const pnlPct = t?.chart?.pnl_pct ?? null;
  return (
    <div>
      <Section step="4" label="복기 루프 · 4단계 거래별 설명" />
      <h2 style={{ fontSize: "clamp(22px,3.6vw,28px)", fontWeight: 700, color: "#0B2E59", margin: "14px 0 8px" }}>거래마다, 왜 잃었는지</h2>
      <p style={{ color: "#8B95A1", fontSize: 16, margin: "0 0 18px" }}>손실 거래를 탭으로 하나씩 넘겨 보세요. 분류기가 걸러낸 피쳐와 심리 신호로 설명해요.</p>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 9 }}>
        <span style={{ flex: "0 0 50px", fontSize: 12, fontWeight: 700, color: "#B0B8C1", paddingTop: 9 }}>유형</span>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
          {([["all", "전체"], ["cut", "손절실패"], ["entry", "진입오류"]] as const).map(([id, label]) => {
            const act = filterType === id; const col = id === "all" ? "#0B2E59" : DOMAIN[id as DomainId].color;
            return <button key={id} onClick={() => { setFilterType(id); setSelTrade(0); }} style={{ cursor: "pointer", fontSize: 13.5, borderRadius: 9, padding: "8px 15px", fontWeight: act ? 600 : 500, background: act ? col : "#F2F4F6", color: act ? "#fff" : "#8B95A1", border: "none" }}>{label}</button>;
          })}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <span style={{ flex: "0 0 50px", fontSize: 12, fontWeight: 700, color: "#B0B8C1", paddingTop: 8 }}>심각도</span>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
          {([["all", "전체 심각도"], ["strong", "강함"], ["moderate", "보통"], ["weak", "약함"]] as const).map(([id, label]) => {
            const act = filterSev === id;
            return <button key={id} onClick={() => { setFilterSev(id); setSelTrade(0); }} style={{ cursor: "pointer", fontSize: 13, borderRadius: 9, padding: "7px 13px", fontWeight: 500, background: act ? "#E8EBED" : "transparent", color: act ? "#191F28" : "#8B95A1", border: "1px solid " + (act ? "transparent" : "#E5E8EB") }}>{label}</button>;
          })}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: "50px 20px", color: "#8B95A1", fontSize: 15, background: "#F2F4F6", borderRadius: 14 }}>해당하는 거래가 없어요. 필터를 바꿔보세요.</div>
      ) : (
        <>
          {/* ── 거래별 미니탭 (1탭 = 1거래). 필터 줄과 다른 맥락이므로 구분선으로 분리 ── */}
          <div style={{ borderTop: "1px solid #ECEEF0", margin: "16px 0 0" }} />
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12, margin: "14px 0 16px" }}>
            <span style={{ flex: "0 0 50px", fontSize: 12, fontWeight: 700, color: "#B0B8C1", paddingTop: 9 }}>거래 {filtered.length}건</span>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {filtered.map((ft, i) => {
                const fm = DOMAIN[ft.type]; const on = i === active;
                return (
                  <button key={ft.trade_id} onClick={() => setSelTrade(i)} style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 7, fontSize: 13, fontWeight: on ? 700 : 500, borderRadius: 10, padding: "8px 13px", background: on ? "#fff" : "#F2F4F6", color: on ? "#191F28" : "#8B95A1", border: "1.5px solid " + (on ? fm.color : "transparent"), boxShadow: on ? "0 1px 4px rgba(0,0,0,.05)" : "none" }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: fm.color, flexShrink: 0 }} />
                    {ft.name || ft.code}
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── 선택된 거래 카드 (가로: 왼쪽 차트 / 오른쪽 설명) ── */}
          {t && (
          <div style={{ overflow: "hidden", background: "#fff", border: "1px solid #E5E8EB", borderLeft: "3px solid " + m.color, borderRadius: 14 }}>
            <div style={{ display: "flex", flexWrap: "wrap" }}>
              {/* 왼쪽: 실거래 차트 + 피쳐 위치 */}
              <div style={{ flex: "1 1 320px", minWidth: 280, background: "#FBFCFD", borderRight: "1px solid #F2F4F6", padding: "16px 14px 10px" }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 9, marginBottom: 4 }}>
                  <span style={{ fontSize: 17, fontWeight: 700 }}>{t.name || t.code}</span>
                  <span style={{ fontSize: 12.5, color: "#8B95A1" }}>{t.code}</span>
                  {pnlPct != null && <span style={{ marginLeft: "auto", fontSize: 15, fontWeight: 700, color: pnlPct < 0 ? "#E2574C" : "#0B8043" }}>{pnlPct > 0 ? "+" : ""}{pnlPct.toFixed(2)}%</span>}
                </div>
                <div style={{ fontSize: 11.5, color: "#8B95A1", marginBottom: 6 }}>진입 {t.date} · 보유구간 실거래</div>
                {t.chart ? <TradeMiniChart chart={t.chart} color={m.color} tint={m.tint} />
                  : <div style={{ height: 150, display: "flex", alignItems: "center", justifyContent: "center", color: "#B0B8C1", fontSize: 13 }}>차트 데이터 없음</div>}
              </div>

              {/* 오른쪽: 분류 근거 + 심리 심화 */}
              <div style={{ flex: "1 1 360px", minWidth: 300, padding: "16px 18px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap", marginBottom: 11 }}>
                  <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 10px 5px 8px", borderRadius: 8, background: m.tint }}>
                    <DomainIcon type={t.type} size={15} /><span style={{ fontSize: 13.5, fontWeight: 600, color: m.color }}>{t.typeName}</span>
                  </div>
                  <span style={{ fontSize: 11.5, fontWeight: 600, borderRadius: 6, padding: "4px 9px", color: "#8B95A1", background: "#F2F4F6" }}>{SEV_LABEL[t.sev] || t.sev}</span>
                  {t.label && <span style={{ fontSize: 11.5, fontWeight: 600, borderRadius: 6, padding: "4px 9px", color: m.color, background: m.tint }}>{t.label}</span>}
                </div>
                <p style={{ fontSize: 14.5, lineHeight: 1.7, color: "#4E5968", margin: "0 0 14px" }}>{t.desc}</p>

                {/* 왜 이 분류인가 — 피쳐 근거 */}
                {t.why?.length > 0 && (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: m.color, marginBottom: 8 }}>왜 {t.typeName}로 봤나: 분류기가 걸러낸 신호</div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {t.why.map((w, k) => (
                        <div key={k} style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13.5, lineHeight: 1.55, color: w.strong ? "#191F28" : "#4E5968", fontWeight: w.strong ? 600 : 400 }}>
                          <span style={{ flexShrink: 0, width: 6, height: 6, borderRadius: "50%", marginTop: 6, background: w.strong ? m.color : "#C4CDD5" }} />
                          <span>{w.text}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 심리 심화 */}
                {t.psych && (
                  <div style={{ background: t.psych.detected ? m.tint : "#F8F9FA", borderRadius: 10, padding: "12px 13px", marginBottom: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: t.psych.evidence.length || t.psych.desc ? 6 : 0 }}>
                      <span style={{ fontSize: 12.5, fontWeight: 700, color: t.psych.detected ? m.color : "#8B95A1" }}>심리 신호 · {t.psych.name}</span>
                      <span style={{ fontSize: 10.5, fontWeight: 700, borderRadius: 5, padding: "2px 7px", color: "#fff", background: t.psych.detected ? m.color : "#B0B8C1" }}>{t.psych.detected ? "감지됨" : "약함"}</span>
                    </div>
                    {t.psych.desc && <p style={{ fontSize: 12.5, lineHeight: 1.6, color: "#8B95A1", margin: "0 0 6px" }}>{t.psych.desc}</p>}
                    {t.psych.evidence.map((e, k) => (
                      <p key={k} style={{ fontSize: 13, lineHeight: 1.6, color: "#4E5968", margin: "4px 0 0" }}>· {e}</p>
                    ))}
                  </div>
                )}

                {/* 손절실패 신호 점수 */}
                {t.signals && (
                  <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
                    {Object.entries(t.signals).map(([k, v]) => {
                      const on = (v ?? 0) > 0.05;
                      return (
                        <div key={k} style={{ flex: "1 1 0", textAlign: "center", borderRadius: 9, padding: "8px 4px", background: on ? "#E7ECF4" : "#F2F4F6", border: "1px solid " + (on ? "#0B2E59" : "transparent") }}>
                          <div style={{ fontSize: 12.5, fontWeight: 600, color: on ? "#0B2E59" : "#B0B8C1" }}>{k}</div>
                          <div style={{ fontSize: 11, color: "#8B95A1", marginTop: 2 }}>{(v ?? 0).toFixed(2)} <span style={{ color: "#C4CDD5" }}>·w{SIG_W[k]}</span></div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* 분류기 라우팅 점수 */}
                {(t.eScore != null && t.cScore != null) && (
                  <div style={{ background: "#F8F9FA", borderRadius: 10, padding: "10px 12px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 7 }}>
                      <span style={{ fontSize: 12, color: "#8B95A1" }}>분류기 라우팅 점수</span>
                      <span style={{ fontSize: 11, fontWeight: 600, borderRadius: 6, padding: "3px 8px", color: "#0B2E59", background: "#EAF0F8" }}>{t.route || "-"} · 신뢰도 {t.conf != null ? Math.round(t.conf * 100) + "%" : "-"}</span>
                    </div>
                    <div style={{ display: "flex", height: 8, borderRadius: 5, overflow: "hidden", background: "#E9ECEF" }}>
                      <div style={{ width: eW + "%", background: "#F0890C" }} /><div style={{ width: cW + "%", background: "#0B2E59" }} />
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 11, color: "#8B95A1" }}>
                      <span>진입오류 {t.eScore?.toFixed(2)}</span><span>손절실패 {t.cScore?.toFixed(2)}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
          )}
        </>
      )}

      {/* ── 다음 단계: 안 본 다른 도메인 되묻기 → 진단 복귀 / 내 성향 ── */}
      {asking ? (
        <div style={{ marginTop: 24, background: "#FFF8F2", border: "1px solid #FBD9BF", borderRadius: 16, padding: "20px 22px" }}>
          <div style={{ fontSize: 15.5, fontWeight: 700, color: "#191F28", marginBottom: 6 }}>아직 안 본 문제가 있어요</div>
          <p style={{ fontSize: 14.5, lineHeight: 1.65, color: "#4E5968", margin: "0 0 16px" }}>
            이번엔 <b style={{ color: DOMAIN[other.id].color }}>{other.name} {other.count}건</b>도 같은 방식으로 분석해 드릴까요? 보고 나서 내 성향으로 넘어가요.
          </p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button onClick={onSeeOther} style={{ cursor: "pointer", fontSize: 14.5, fontWeight: 600, borderRadius: 11, padding: "12px 20px", border: "none", background: DOMAIN[other.id].color, color: "#fff" }}>네, {other.name}도 볼게요 →</button>
            <button onClick={onToProfile} style={{ cursor: "pointer", fontSize: 14.5, fontWeight: 600, borderRadius: 11, padding: "12px 20px", border: "1.5px solid #E5E8EB", background: "#fff", color: "#8B95A1" }}>아니요, 내 성향 볼게요</button>
          </div>
        </div>
      ) : (
        <button onClick={() => (shouldAsk ? setAsking(true) : onToProfile())} style={{ cursor: "pointer", width: "100%", marginTop: 24, fontSize: 15.5, fontWeight: 700, borderRadius: 12, padding: "15px", border: "none", background: "#F5500A", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
          총평 · 내 성향 보러 가기 →
        </button>
      )}
    </div>
  );
}

// ── ⑤ PROFILE ────────────────────────────────────────────────────────────────
function CompareBar({ user, pop, color }: { user: number; pop: number; color: string }) {
  // 본인 발생률(채움) + 모집단 평균 위치(세로 마커)를 한 막대에 표시.
  const max = Math.max(100, user, pop);
  return (
    <div style={{ position: "relative", height: 10, borderRadius: 6, background: "#EEF1F4", overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: (user / max) * 100 + "%", background: color, borderRadius: 6 }} />
      <div style={{ position: "absolute", left: (pop / max) * 100 + "%", top: -2, bottom: -2, width: 2, background: "#191F28" }} title="모집단 평균" />
    </div>
  );
}

function ProfileView({ disp, userName }: { disp: Disposition | null; userName: string }) {
  if (!disp) return <div><Section step="5" label="복기 루프 · 5단계 내 성향 프로파일" /><Loading /></div>;
  const dm = DOMAIN[disp.dominant.id];
  // 헤드라인은 첫 콤마 뒤에서만 줄바꿈하고, 그다음은 한 줄로 이어지게.
  const ci = disp.headline.indexOf(", ");
  const h1 = ci >= 0 ? disp.headline.slice(0, ci + 1) : disp.headline;
  const h2 = ci >= 0 ? disp.headline.slice(ci + 2) : "";
  const psychRows = [
    { name: "처분효과", sub: "손실을 오래 끄는 심리", v: disp.psych.disposition, color: DOMAIN.cut.color },
    { name: "리벤지", sub: "직전 손실 만회 충동", v: disp.psych.revenge, color: DOMAIN.entry.color },
  ];
  return (
    <div>
      <Section step="5" label="복기 루프 · 5단계 내 성향 프로파일" />
      <h2 style={{ fontSize: "clamp(22px,3.8vw,30px)", fontWeight: 700, color: "#0B2E59", lineHeight: 1.32, margin: "14px 0 10px" }}>{userName}님의 최종 성향</h2>
      <p style={{ color: "#4E5968", fontSize: 16, lineHeight: 1.7, margin: "0 0 20px" }}>{h1}{h2 && <br />}{h2}</p>

      {/* 주된 실수 도메인 */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, background: dm.tint, borderRadius: 14, padding: "14px 16px", marginBottom: 22 }}>
        <div style={{ width: 38, height: 38, borderRadius: 11, display: "flex", alignItems: "center", justifyContent: "center", background: "#fff" }}><DomainIcon type={disp.dominant.id} size={20} /></div>
        <div>
          <div style={{ fontSize: 12.5, color: "#8B95A1" }}>주로 반복되는 실수</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: dm.color }}>{disp.dominant.name} <span style={{ fontSize: 13, color: "#8B95A1", fontWeight: 500 }}>· 손실의 {disp.dominant.pct}%</span></div>
        </div>
      </div>

      {/* 모집단 대비 유독 잘 걸리는 피쳐 */}
      <div style={{ fontSize: 16, fontWeight: 700, color: "#191F28", marginBottom: 4 }}>남들보다 유독 잘 걸리는 지점</div>
      <p style={{ fontSize: 13, color: "#8B95A1", margin: "0 0 14px" }}>10명 평균(│ 검은 선)과 비교한 {userName}님의 발생률입니다.</p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 12, marginBottom: 28 }}>
        {disp.signature.map((s, i) => {
          const c = DOMAIN[s.domain].color;
          const over = s.ratio >= 1.15;
          return (
            <div key={i} style={{ background: "#fff", border: "1px solid #E5E8EB", borderRadius: 14, padding: "15px 16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 11 }}>
                <span style={{ width: 9, height: 9, borderRadius: "50%", background: c, flexShrink: 0 }} />
                <span style={{ fontSize: 14.5, fontWeight: 700 }}>{s.label}</span>
                {s.reliable && over
                  ? <span style={{ marginLeft: "auto", fontSize: 11.5, fontWeight: 700, color: "#fff", background: c, borderRadius: 6, padding: "3px 8px" }}>평균 ×{s.ratio}배</span>
                  : over
                    ? <span style={{ marginLeft: "auto", fontSize: 11, fontWeight: 600, color: c, background: DOMAIN[s.domain].tint, borderRadius: 6, padding: "3px 8px" }}>남들에겐 드문 신호</span>
                    : <span style={{ marginLeft: "auto", fontSize: 11, fontWeight: 600, color: "#8B95A1", background: "#F2F4F6", borderRadius: 6, padding: "3px 8px" }}>평균 수준</span>}
              </div>
              <CompareBar user={s.user_pct} pop={s.pop_pct} color={c} />
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 7, fontSize: 12, color: "#8B95A1" }}>
                <span style={{ color: "#191F28", fontWeight: 600 }}>본인 {s.user_pct}%</span>
                <span>10명 평균 {s.pop_pct}% · {s.count}건</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* 심리 신호 vs 평균 */}
      <div style={{ fontSize: 16, fontWeight: 700, color: "#191F28", marginBottom: 12 }}>심리 신호</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: 12, marginBottom: 28 }}>
        {psychRows.map((r, i) => (
          <div key={i} style={{ background: "#fff", border: "1px solid #E5E8EB", borderRadius: 14, padding: "15px 16px" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 7, marginBottom: 10 }}>
              <span style={{ fontSize: 14.5, fontWeight: 700, color: r.color }}>{r.name}</span>
              <span style={{ fontSize: 12, color: "#8B95A1" }}>{r.sub}</span>
              <span style={{ marginLeft: "auto", fontSize: 11.5, fontWeight: 600, color: r.v.user_pct > r.v.pop_pct ? r.color : "#8B95A1" }}>{r.v.user_pct > r.v.pop_pct ? "평균 이상" : "평균 이하"}</span>
            </div>
            <CompareBar user={r.v.user_pct} pop={r.v.pop_pct} color={r.color} />
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 7, fontSize: 12, color: "#8B95A1" }}>
              <span style={{ color: "#191F28", fontWeight: 600 }}>본인 {r.v.user_pct}%</span>
              <span>10명 평균 {r.v.pop_pct}%</span>
            </div>
          </div>
        ))}
      </div>

      {/* 최종 솔루션 */}
      {disp.solutions.length > 0 && (
        <div style={{ background: "#fff", border: "1px solid #E5E8EB", borderRadius: 16, padding: "20px 22px", marginBottom: 18 }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#0B2E59", marginBottom: 4 }}>그래서, 이렇게 고쳐봐요</div>
          <p style={{ fontSize: 13, color: "#8B95A1", margin: "0 0 14px" }}>{userName}님의 성향에 맞춘 최종 솔루션이에요.</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {disp.solutions.map((s, i) => (
              <div key={i} style={{ display: "flex", gap: 11, alignItems: "flex-start", background: "#0B2E59", borderRadius: 11, padding: "13px 14px" }}>
                <span style={{ flexShrink: 0, width: 22, height: 22, borderRadius: "50%", background: "#F5500A", color: "#fff", fontSize: 12.5, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" }}>{i + 1}</span>
                <span style={{ fontSize: 14.5, lineHeight: 1.6, color: "#EAF0F8" }}>{s}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "inline-flex", alignItems: "center", gap: 7, background: "#F2F4F6", borderRadius: 9, padding: "9px 13px" }}>
        <span style={{ fontSize: 13, color: "#4E5968", fontWeight: 500 }}>이 성향이 곧 실시간 알림(예측기)의 학습 근거가 돼요.</span>
      </div>
    </div>
  );
}

// ── ⑥ ALERTS (실시간 보유 추적) ──────────────────────────────────────────────
function HoldingCard({ h }: { h: Holding }) {
  const navy = DOMAIN.cut.color;
  const alert = h.status === "alert";
  const accent = alert ? "#F5500A" : "#C4CDD5";
  const pos = h.pct >= 0;
  return (
    <div style={{ background: "#fff", borderRadius: 18, overflow: "hidden", borderLeft: "4px solid " + accent, boxShadow: "0 4px 16px rgba(0,0,0,.07)", animation: "wlslidein .45s ease both" }}>
      <div style={{ background: "#FBFCFD", borderBottom: "1px solid #F2F4F6", padding: "13px 15px 6px" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 2 }}>
          <span style={{ fontSize: 15.5, fontWeight: 700 }}>{h.name}</span>
          <span style={{ fontSize: 12, color: "#8B95A1" }}>{h.code}</span>
          <span style={{ marginLeft: "auto", fontSize: 14.5, fontWeight: 700 }}>₩{h.current_price.toLocaleString()}</span>
          <span style={{ fontSize: 12.5, fontWeight: 700, color: pos ? "#0B8043" : "#E2574C" }}>{pos ? "+" : ""}{h.pct}%</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4 }}>
          <span style={{ fontSize: 11, color: "#8B95A1" }}>{h.qty}주 보유 · 손절선 ₩{h.stop.toLocaleString()}</span>
          <span style={{ marginLeft: "auto", fontSize: 10.5, fontWeight: 700, borderRadius: 5, padding: "2px 7px", color: alert ? "#fff" : (pos ? "#0B8043" : "#8B95A1"), background: alert ? "#F5500A" : (pos ? "#E7F4ED" : "#F2F4F6") }}>
            {alert ? "손절 경고" : pos ? "이익 추적 중" : "추적 중"}
          </span>
        </div>
        {h.chart && <AlertMiniChart chart={h.chart} color={navy} />}
      </div>
      <div style={{ padding: "12px 15px" }}>
        {alert && h.risk ? (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <div style={{ width: 20, height: 20, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", background: "#F5500A" }}>
                <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round"><polyline points="3 7 9 13 13 9 21 17" /><polyline points="21 12 21 17 16 17" /></svg>
              </div>
              <span style={{ fontSize: 12, fontWeight: 600 }}>왜 잃었지?</span>
              <span style={{ marginLeft: "auto", fontSize: 11, fontWeight: 700, color: "#fff", background: "#F5500A", borderRadius: 6, padding: "3px 8px" }}>예측 경고</span>
            </div>
            <div style={{ fontSize: 14, lineHeight: 1.6, color: "#4E5968", marginBottom: 10 }}>{h.risk.message}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 11.5, color: "#8B95A1" }}>위험도</span>
              <div style={{ flex: 1, height: 6, borderRadius: 4, background: "#EEF1F4", overflow: "hidden" }}><div style={{ width: h.risk.score + "%", height: "100%", background: "#F5500A" }} /></div>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#F5500A" }}>{h.risk.score}</span>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
              {h.risk.reasons.map((r, k) => <span key={k} style={{ fontSize: 11, color: "#4E5968", background: "#F2F4F6", borderRadius: 5, padding: "3px 7px" }}>{r}</span>)}
            </div>
          </>
        ) : (
          <div style={{ fontSize: 13, color: "#8B95A1", lineHeight: 1.55 }}>
            {pos ? "아직 손절선 위에서 이익 구간이에요. 떨어지면 바로 알려드릴게요." : "손절선 위에서 추적 중이에요. 손절선에 닿으면 알림을 띄울게요."}
          </div>
        )}
      </div>
    </div>
  );
}

function PlanCard({ a }: { a: Alert }) {
  const color = DOMAIN[a.type].color; const ch = a.chart;
  return (
    <div style={{ background: "#fff", borderRadius: 18, overflow: "hidden", borderLeft: "4px solid " + color, boxShadow: "0 4px 16px rgba(0,0,0,.07)", animation: "wlslidein .45s ease both" }}>
      {ch && (
        <div style={{ background: "#FBFCFD", borderBottom: "1px solid #F2F4F6", padding: "13px 15px 6px" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 2 }}>
            <span style={{ fontSize: 15.5, fontWeight: 700 }}>{a.name}</span>
            <span style={{ fontSize: 12, color: "#8B95A1" }}>{a.code}</span>
            <span style={{ marginLeft: "auto", fontSize: 14.5, fontWeight: 700 }}>₩{ch.marker.price.toLocaleString()}</span>
          </div>
          <div style={{ fontSize: 11, color: "#8B95A1", marginBottom: 4 }}>매수 예정 · 진입 시점 추적</div>
          <AlertMiniChart chart={ch} color={color} />
        </div>
      )}
      <div style={{ padding: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 9 }}>
          <div style={{ width: 22, height: 22, borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center", background: "#F5500A" }}>
            <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round"><polyline points="3 7 9 13 13 9 21 17" /><polyline points="21 12 21 17 16 17" /></svg>
          </div>
          <span style={{ fontSize: 12, fontWeight: 600 }}>왜 잃었지?</span>
          <span style={{ fontSize: 12.5, color, fontWeight: 500 }}>· {a.kind}</span>
          <span style={{ marginLeft: "auto", fontSize: 11, fontWeight: 700, color: "#fff", background: "#F5500A", borderRadius: 6, padding: "3px 8px" }}>예측 알림</span>
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, lineHeight: 1.45, marginBottom: 5 }}>{a.title}</div>
        <div style={{ fontSize: 14, lineHeight: 1.6, color: "#4E5968" }}>{a.body}</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 10 }}>
          {a.reasons.map((r, k) => <span key={k} style={{ fontSize: 11, color: "#4E5968", background: "#F2F4F6", borderRadius: 5, padding: "3px 7px" }}>{r}</span>)}
        </div>
      </div>
    </div>
  );
}

// 한국식 등락 색 (상승=빨강, 하락=파랑)
const UP = "#F0454A", DOWN = "#2D7FF9";
const krColor = (v: number) => (v > 0 ? UP : v < 0 ? DOWN : "#8B95A1");

function OrderRow({ label, value, step }: { label: string; value: string; step?: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "#fff", border: "1px solid #E5E8EB", borderRadius: 10, padding: "10px 12px" }}>
      <span style={{ fontSize: 11.5, color: "#8B95A1" }}>{label}</span>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {step && <span style={{ width: 18, height: 18, borderRadius: 5, background: "#F2F4F6", color: "#8B95A1", fontSize: 13, display: "flex", alignItems: "center", justifyContent: "center" }}>−</span>}
        <span style={{ fontSize: 14, fontWeight: 700 }}>{value}</span>
        {step && <span style={{ width: 18, height: 18, borderRadius: 5, background: "#F2F4F6", color: "#8B95A1", fontSize: 13, display: "flex", alignItems: "center", justifyContent: "center" }}>+</span>}
      </div>
    </div>
  );
}

// 증권사 앱 목업 (레퍼런스 기반). scenario='stop' 보유목록 / 'entry' 매수주문. 우상단 종 알림.
function PhoneApp({ scenario, holdings, plan, highlightCode, opened, onBell }: {
  scenario: "stop" | "entry"; holdings: Holding[]; plan: Alert | null; highlightCode?: string; opened: boolean; onBell: () => void;
}) {
  const isStop = scenario === "stop";
  const bell = isStop ? DOMAIN.cut.color : DOMAIN.entry.color;
  const ringing = !opened;
  const price = plan?.chart?.marker.price ?? 0;
  const tabs = ["국내주식", "해외주식", "연금·상품"];
  return (
    <div style={{ position: "relative", width: 332, flexShrink: 0, padding: 10, background: "linear-gradient(160deg,#23262E,#15171C)", borderRadius: 46, boxShadow: "0 22px 60px rgba(11,46,89,.26)" }}>
      <div style={{ background: "#fff", borderRadius: 37, overflow: "hidden", height: 686, display: "flex", flexDirection: "column" }}>
        {/* 상태바 + 다이나믹 아일랜드 */}
        <div style={{ position: "relative", height: 38, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 22px" }}>
          <span style={{ fontSize: 12.5, fontWeight: 700, color: "#191F28", letterSpacing: .3 }}>9:41</span>
          <div style={{ position: "absolute", top: 9, left: "50%", transform: "translateX(-50%)", width: 86, height: 20, background: "#15171C", borderRadius: 13 }} />
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <svg width={16} height={11} viewBox="0 0 18 12" fill="#191F28"><rect x="0" y="7" width="3" height="5" rx="1" /><rect x="4.5" y="4.5" width="3" height="7.5" rx="1" /><rect x="9" y="2" width="3" height="10" rx="1" /><rect x="13.5" y="0" width="3" height="12" rx="1" opacity=".35" /></svg>
            <svg width={15} height={11} viewBox="0 0 16 12" fill="none" stroke="#191F28" strokeWidth="1.4"><path d="M1 4.5a10 10 0 0 1 14 0M3.5 7a6.5 6.5 0 0 1 9 0M8 9.5h.01" strokeLinecap="round" /></svg>
            <div style={{ display: "flex", alignItems: "center", gap: 1 }}><div style={{ width: 18, height: 10, borderRadius: 3, border: "1.3px solid #191F28", padding: 1.5 }}><div style={{ width: "82%", height: "100%", background: "#191F28", borderRadius: 1 }} /></div><div style={{ width: 1.5, height: 4, background: "#191F28", borderRadius: 1 }} /></div>
          </div>
        </div>
        {/* 검색바 + 종 */}
        <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "6px 15px 10px" }}>
          <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 7, background: "#F2F4F6", borderRadius: 11, padding: "9px 12px" }}>
            <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="#8B95A1" strokeWidth={2.2} strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
            <span style={{ fontSize: 12, color: "#B0B8C1" }}>주식·상품·뉴스 검색</span>
          </div>
          <button onClick={onBell} title="알림" style={{ position: "relative", width: 38, height: 38, borderRadius: 11, border: "none", cursor: "pointer", background: ringing ? bell + "1A" : "transparent", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width={21} height={21} viewBox="0 0 24 24" fill="none" stroke={ringing ? bell : "#4E5968"} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" style={{ transformOrigin: "50% 3px", animation: ringing ? "wlbell 1.1s ease infinite" : "none" }}>
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
            {ringing && <span style={{ position: "absolute", top: 6, right: 7, minWidth: 9, height: 9, borderRadius: "50%", background: bell, border: "2px solid #fff", animation: "wlpop .35s ease" }} />}
          </button>
        </div>
        {/* 탭 */}
        <div style={{ display: "flex", gap: 16, padding: "0 16px", borderBottom: "1px solid #F2F4F6" }}>
          {tabs.map((t, i) => (
            <div key={t} style={{ position: "relative", padding: "9px 0 11px", fontSize: 13.5, fontWeight: i === 0 ? 700 : 500, color: i === 0 ? "#191F28" : "#B0B8C1" }}>
              {t}
              {i === 0 && <div style={{ position: "absolute", left: 0, right: 0, bottom: -1, height: 2.5, background: "#191F28", borderRadius: 2 }} />}
            </div>
          ))}
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", color: "#C4CDD5", fontSize: 16 }}>⋯</div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        {isStop ? (
          <div style={{ padding: "12px 14px 18px" }}>
            <div style={{ display: "flex", alignItems: "baseline", marginBottom: 4 }}>
              <span style={{ fontSize: 14, fontWeight: 800, color: "#191F28" }}>내 보유 종목</span>
              <span style={{ fontSize: 11.5, color: "#8B95A1", marginLeft: "auto" }}>실시간 ·  평가손익</span>
            </div>
            <div style={{ display: "flex", gap: 6, margin: "6px 0 12px" }}>
              {["보유순", "손익순", "관심"].map((s, i) => (
                <span key={s} style={{ fontSize: 11.5, fontWeight: i === 0 ? 700 : 500, borderRadius: 7, padding: "5px 10px", background: i === 0 ? "#EAF0F8" : "#F8F9FA", color: i === 0 ? "#0B2E59" : "#8B95A1" }}>{s}</span>
              ))}
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              {holdings.map((h, i) => {
                const hot = h.code === highlightCode;
                return (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 11, padding: "11px 8px", borderTop: i ? "1px solid #F5F6F7" : "none", borderRadius: hot ? 10 : 0, background: hot ? bell + "12" : "transparent", boxShadow: hot ? "inset 3px 0 0 " + bell : "none" }}>
                    <div style={{ width: 30, height: 30, borderRadius: 9, background: "#F2F4F6", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 800, color: "#8B95A1", flexShrink: 0 }}>{h.name.slice(0, 1)}</div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{h.name}</div>
                      <div style={{ fontSize: 11, color: "#8B95A1" }}>{h.qty}주 · 평단 ₩{h.entry_price.toLocaleString()}</div>
                    </div>
                    <div style={{ marginLeft: "auto", textAlign: "right" }}>
                      <div style={{ fontSize: 13.5, fontWeight: 700 }}>{h.current_price.toLocaleString()}</div>
                      <div style={{ fontSize: 11.5, fontWeight: 700, color: krColor(h.pct) }}>{h.pct > 0 ? "▲" : h.pct < 0 ? "▼" : ""} {Math.abs(h.pct)}%</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : plan ? (
          <div style={{ padding: "14px 15px 18px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
              <div style={{ width: 26, height: 26, borderRadius: 8, background: "#F2F4F6", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 800, color: "#8B95A1" }}>{(plan.name || "").slice(0, 1)}</div>
              <span style={{ fontSize: 15.5, fontWeight: 800 }}>{plan.name}</span>
              <span style={{ fontSize: 11, color: "#8B95A1" }}>{plan.code}</span>
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 14 }}>
              <span style={{ fontSize: 24, fontWeight: 800, color: UP }}>{price.toLocaleString()}</span>
              <span style={{ fontSize: 12.5, fontWeight: 700, color: UP }}>▲ 상승 추적 중</span>
            </div>
            <div style={{ display: "flex", marginBottom: 13, borderRadius: 11, overflow: "hidden", border: "1px solid #E5E8EB" }}>
              <div style={{ flex: 1, textAlign: "center", padding: "10px", fontSize: 13.5, fontWeight: 700, background: UP, color: "#fff" }}>매수</div>
              <div style={{ flex: 1, textAlign: "center", padding: "10px", fontSize: 13.5, fontWeight: 600, color: "#8B95A1", background: "#fff" }}>매도</div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 13 }}>
              <OrderRow label="주문가격" value={`${price.toLocaleString()}`} step />
              <OrderRow label="주문수량" value="10주" step />
              <OrderRow label="주문금액" value={`₩${(price * 10).toLocaleString()}`} />
            </div>
            <div style={{ background: UP, color: "#fff", textAlign: "center", padding: "14px", borderRadius: 12, fontSize: 15, fontWeight: 700 }}>현금 매수</div>
          </div>
        ) : (
          <div style={{ padding: "40px 20px", textAlign: "center", color: "#8B95A1", fontSize: 13 }}>예정된 매수가 없어요.</div>
        )}
        </div>
        {/* 하단 탭바 */}
        <div style={{ display: "flex", justifyContent: "space-around", alignItems: "center", padding: "8px 6px 4px", borderTop: "1px solid #F2F4F6" }}>
          {[
            { paths: ["M3 11l9-8 9 8", "M5 10v10h14V10"], label: "홈", on: false },
            { paths: ["M3 17l5-5 4 4 8-8", "M21 8v5h-5"], label: "주식", on: true },
            { paths: ["M20.8 5.6a5.5 5.5 0 0 0-8.8-1.4 5.5 5.5 0 0 0-8.8 1.4c-1.6 3.2.8 6.4 8.8 12.4 8-6 10.4-9.2 8.8-12.4z"], label: "관심", on: false },
            { paths: ["M4 5h16v14H4z", "M4 10h16", "M9 5v14"], label: "내자산", on: false },
            { paths: ["M4 6h16M4 12h16M4 18h16"], label: "전체", on: false },
          ].map((t, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3, color: t.on ? "#0B2E59" : "#B0B8C1" }}>
              <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
                {t.paths.map((d, k) => <path key={k} d={d} />)}
              </svg>
              <span style={{ fontSize: 9.5, fontWeight: t.on ? 700 : 500 }}>{t.label}</span>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "center", padding: "3px 0 8px" }}><div style={{ width: 110, height: 4.5, borderRadius: 3, background: "#191F28" }} /></div>
      </div>
    </div>
  );
}

function AlertsView({ data }: { data: HoldingsResp | null }) {
  const [scenario, setScenario] = useState<"stop" | "entry">("stop");
  const [opened, setOpened] = useState(false);
  const holdings = data?.holdings ?? [];
  const plans = data?.plans ?? [];
  // 경고 카드에 올릴 보유. status==='alert' 가 없을 때 그냥 holdings[0] 을 집으면
  // 크게 오른 종목이 뽑혀서, 손절선이 가격대보다 한참 아래에 떨어져 그려지고
  // "손절실패 징후 감지"라는 제목과도 어긋난다. 손절선에 가장 가까운(또는 이미 밑인)
  // 종목을 고른다.
  const stopHolding =
    holdings.find((h) => h.status === "alert") ??
    [...holdings].sort((a, b) => a.current_price / a.stop - b.current_price / b.stop)[0];
  const entryPlan = plans[0] ?? null;
  const hasStop = !!stopHolding, hasEntry = !!entryPlan;
  // 사용자/시나리오 바뀌면 닫고, 가능한 시나리오로 기본 전환
  useEffect(() => { setOpened(false); }, [scenario, data?.user_id]);
  useEffect(() => { if (!hasStop && hasEntry) setScenario("entry"); }, [hasStop, hasEntry]);
  // 아키텍처 연동(2단계로 또렷하게):
  //  · 감시 중(종 울리는 중) → 실시간 추적 → 단일 예측기
  //  · 종 클릭(경고 발화)   → 해당 경고(손절/진입) → 사용자 알림  (발화된 곳만)
  useEffect(() => {
    if (!opened) { archSet(["s-track", "s-feat", "s-pred"], "실시간 추적 → 피처 계산 → 예측기 감시 중"); return; }
    if (scenario === "stop") archSet(["s-stop", "s-notify"], "② 손절 경고 → 사용자 알림");
    else archSet(["s-entry", "s-notify"], "① 진입오류 경고 → 사용자 알림");
  }, [scenario, opened]);
  if (!data) return <div style={{ maxWidth: 560, margin: "0 auto" }}><Loading /></div>;

  const isStop = scenario === "stop";
  const accent = isStop ? DOMAIN.cut.color : DOMAIN.entry.color;
  const card = isStop ? (stopHolding && <HoldingCard h={stopHolding} />) : (entryPlan && <PlanCard a={entryPlan} />);
  const Toggle = ({ id, label, on }: { id: "stop" | "entry"; label: string; on: boolean }) => (
    <button onClick={() => on && setScenario(id)} disabled={!on}
      style={{ cursor: on ? "pointer" : "not-allowed", fontSize: 13.5, fontWeight: scenario === id ? 700 : 500, borderRadius: 10, padding: "9px 16px", border: "1.5px solid " + (scenario === id ? (id === "stop" ? DOMAIN.cut.color : DOMAIN.entry.color) : "transparent"), background: scenario === id ? "#fff" : "#F2F4F6", color: !on ? "#C4CDD5" : scenario === id ? (id === "stop" ? DOMAIN.cut.color : DOMAIN.entry.color) : "#8B95A1" }}>
      {label}
    </button>
  );

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 13.5, color: "#8B95A1", fontWeight: 500, justifyContent: "center" }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#0B2E59" }} />알림 루프 · 실시간
      </div>
      <h2 style={{ fontSize: "clamp(22px,3.8vw,28px)", fontWeight: 700, color: "#0B2E59", lineHeight: 1.32, margin: "14px 0 10px", textAlign: "center" }}>실시간으로 예측하고,<br />앱이 미리 잡아줘요</h2>
      <p style={{ color: "#8B95A1", fontSize: 15.5, lineHeight: 1.65, margin: "0 auto 22px", maxWidth: 520, textAlign: "center" }}>증권사 앱을 쓰는 중 위험 순간이 오면 여기서 울려요.<br />종을 눌러 예측 알림을 확인하세요.</p>

      <div style={{ display: "flex", justifyContent: "center", gap: 8, marginBottom: 8 }}>
        <Toggle id="stop" label="손절실패 시나리오" on={hasStop} />
        <Toggle id="entry" label="진입오류 시나리오" on={hasEntry} />
      </div>
      <div style={{ textAlign: "center", fontSize: 12.5, color: opened ? "#B0B8C1" : accent, fontWeight: 600, marginBottom: 18, minHeight: 18 }}>
        {opened ? "예측 알림이 도착했어요" : "🔔 앱 우상단의 종이 울리고 있어요. 눌러보세요"}
      </div>

      <div style={{ display: "flex", justifyContent: "center", alignItems: "flex-start", gap: opened ? 22 : 0, transition: "gap .45s cubic-bezier(.4,0,.2,1)" }}>
        <PhoneApp scenario={scenario} holdings={holdings} plan={entryPlan} highlightCode={stopHolding?.code} opened={opened} onBell={() => setOpened(true)} />
        <div style={{ width: opened ? 392 : 0, opacity: opened ? 1 : 0, overflow: "hidden", transition: "width .45s cubic-bezier(.4,0,.2,1), opacity .4s ease" }}>
          <div style={{ width: 392 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 10 }}>
              <span style={{ width: 24, height: 24, borderRadius: 8, background: accent, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></svg>
              </span>
              <span style={{ fontSize: 13.5, fontWeight: 700, color: accent }}>{isStop ? "손절실패 징후 감지" : "진입오류 징후 감지"}</span>
              <span style={{ marginLeft: "auto", fontSize: 11.5, color: "#8B95A1" }}>6/25 11:00</span>
            </div>
            {opened && <div style={{ animation: "wlcardin .45s ease both" }}>{card}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 공용 ─────────────────────────────────────────────────────────────────────
function Stat({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div style={{ background: "#F2F4F6", borderRadius: 14, padding: 18 }}>
      <div style={{ fontSize: 13.5, color: "#8B95A1", marginBottom: 9 }}>{label}</div>
      <div style={{ fontSize: 30, fontWeight: 700, color: "#0B2E59" }}>{value}<span style={{ fontSize: 16, color: "#8B95A1", marginLeft: 3, fontWeight: 500 }}>{unit}</span></div>
    </div>
  );
}
function Loading() { return <div style={{ color: "#8B95A1", fontSize: 15, padding: "40px 0", textAlign: "center" }}>불러오는 중…</div>; }

// 완료 화면 2카드용: 손실 거래에서 도메인별 빈도+총손실금을 직접 집계하고 두 축의 winner 를 뽑는다.
// 동점 시 entry 우선(백엔드 _interaction_dto 의 order 와 동일).
type Winners = { freq: DomainId; amount: DomainId; stats: Record<DomainId, { count: number; amount: number }> };
function statsFromTrades(trades: Trade[]): Winners | null {
  if (!trades.length) return null;
  const stats: Record<DomainId, { count: number; amount: number }> = {
    entry: { count: 0, amount: 0 }, cut: { count: 0, amount: 0 },
  };
  for (const t of trades) {
    const s = stats[t.type];
    if (!s) continue;
    s.count += 1;
    s.amount += Math.abs(t.loss ?? 0);
  }
  const order: DomainId[] = ["entry", "cut"];
  const freq = order.reduce((a, b) => (stats[b].count > stats[a].count || (stats[b].count === stats[a].count && stats[b].amount > stats[a].amount)) ? b : a);
  const amount = order.reduce((a, b) => (stats[b].amount > stats[a].amount || (stats[b].amount === stats[a].amount && stats[b].count > stats[a].count)) ? b : a);
  return { freq, amount, stats };
}

// 원화 축약: 1.2억원 / 1,234만원 / 5,600원
function won(n?: number | null): string {
  if (n == null) return "-";
  const a = Math.abs(n);
  if (a >= 1e8) return (n / 1e8).toFixed(a >= 1e9 ? 0 : 1).replace(/\.0$/, "") + "억원";
  if (a >= 1e4) return Math.round(n / 1e4).toLocaleString() + "만원";
  return Math.round(n).toLocaleString() + "원";
}

const lbl: CSSProperties = { display: "block", fontSize: 14, color: "#8B95A1", margin: "0 0 7px", fontWeight: 500 };
const inp: CSSProperties = { width: "100%", background: "#F2F4F6", border: "1px solid transparent", borderRadius: 12, padding: "15px 16px", fontSize: 16, color: "#191F28" };
const primaryBtn: CSSProperties = { width: "100%", background: "#F5500A", color: "#fff", border: "none", borderRadius: 14, padding: 16, fontSize: 16, fontWeight: 600, cursor: "pointer" };
