"use client";

import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import {
  api, type Alert, type AllTrade, type Dashboard, type Trade, type UserItem, type DomainId, type Disposition,
} from "@/lib/api";
import { DOMAIN, SEV_LABEL, DomainIcon, Logo, Section, LossBars, TradeMiniChart } from "@/components/why/ui";

const ROUTES = ["login", "consent", "upload", "analyze", "dashboard", "trades", "profile", "alerts"] as const;
type Screen = (typeof ROUTES)[number];

const NAV_A = [
  { id: "upload", num: "①", label: "업로드" },
  { id: "analyze", num: "②", label: "분석" },
  { id: "dashboard", num: "③", label: "진단" },
  { id: "trades", num: "④", label: "거래별" },
  { id: "profile", num: "⑤", label: "내 성향" },
] as const;
const NAV_B = [{ id: "alerts", num: "⑥", label: "실시간 알림" }] as const;

export default function Home() {
  const [screen, setScreen] = useState<Screen>("login");
  const [users, setUsers] = useState<UserItem[]>([]);
  const [user, setUser] = useState<string>("");
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [allTrades, setAllTrades] = useState<AllTrade[]>([]);
  const [disp, setDisp] = useState<Disposition | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
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
      let id = (ROUTES.includes(raw as Screen) ? raw : "login") as Screen;
      // 로그인 → 약관 동의를 직접 거치지 않으면 이후 화면으로 못 넘어간다(새로고침·URL 직접입력 포함)
      if (id !== "login" && !authedRef.current) id = "login";
      else if (id !== "login" && id !== "consent" && !consentRef.current) id = "consent";
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
    api.alerts(u).then((d) => setAlerts(d.alerts)).catch(() => setAlerts([]));
  }, []);
  useEffect(() => { loadUser(user); }, [user, loadUser]);

  // 분석 진행 애니메이션 — 4단계까지만 자동, 완료 화면으로는 버튼으로 수동 전환.
  // analyzedRef 로 한 번 끝낸 분석은 화면 재진입 시 다시 돌리지 않는다.
  useEffect(() => {
    if (screen !== "analyze") return;
    if (analyzedRef.current) return;
    setProgressStep(0); setShowResult(false);
    const STEP_MS = 1500; // 사람이 단계 문구를 읽을 시간 확보
    const ts = [1, 2, 3].map((n) => setTimeout(() => setProgressStep(n), STEP_MS * n));
    ts.push(setTimeout(() => { setProgressStep(4); analyzedRef.current = true; }, STEP_MS * 4));
    return () => ts.forEach(clearTimeout);
  }, [screen]);

  const showNav = !(screen === "login" || screen === "consent");
  const curUserName = users.find((u) => u.id === user)?.name || "";

  return (
    <div style={{ minHeight: "100vh", background: "#fff", color: "#191F28" }}>
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
            </nav>
          </div>
        </header>
      )}

      <main style={{ maxWidth: 1080, margin: "0 auto", padding: "28px clamp(16px,4vw,40px) 96px" }}>
        {err && <div style={{ background: "#FFF3EC", color: "#F5500A", border: "1px solid #FBD9BF", borderRadius: 12, padding: "12px 14px", marginBottom: 18, fontSize: 14 }}>
          백엔드 연결 오류: {err} — <b>uvicorn analysis.api.main:app --port 8000</b> 실행 중인지 확인하세요.
        </div>}

        {screen === "login" && <Login onLogin={() => { setAuthed(true); go("consent"); }} onDemo={() => { if (users[0]) setUser(users[0].id); setAuthed(true); go("consent"); }} />}
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
        {screen === "alerts" && <AlertsView alerts={alerts} />}
      </main>
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

// ── LOGIN ────────────────────────────────────────────────────────────────────
function Login({ onLogin, onDemo }: { onLogin: () => void; onDemo: () => void }) {
  const [phone, setPhone] = useState("");
  const [pw, setPw] = useState("");
  const ready = phone.trim().length > 0 && pw.length > 0;
  return (
    <div style={{ maxWidth: 400, margin: "0 auto", padding: "48px 2px 40px" }}>
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
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: m.color, marginBottom: 8 }}>왜 {t.typeName}로 봤나 — 분류기가 걸러낸 신호</div>
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
                      <span style={{ fontSize: 11, fontWeight: 600, borderRadius: 6, padding: "3px 8px", color: "#0B2E59", background: "#EAF0F8" }}>{t.route || "—"} · 신뢰도 {t.conf != null ? Math.round(t.conf * 100) + "%" : "—"}</span>
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

// ── ⑥ ALERTS ─────────────────────────────────────────────────────────────────
function AlertsView({ alerts }: { alerts: Alert[] }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 13.5, color: "#8B95A1", fontWeight: 500, justifyContent: "center" }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#0B2E59" }} />알림 루프 · 실시간
      </div>
      <h2 style={{ fontSize: "clamp(22px,3.8vw,28px)", fontWeight: 700, color: "#0B2E59", lineHeight: 1.32, margin: "14px 0 10px", textAlign: "center" }}>다음 실수를 하려는 순간,<br />이렇게 알려드려요</h2>
      <p style={{ color: "#8B95A1", fontSize: 15.5, lineHeight: 1.65, margin: "0 auto 28px", maxWidth: 480, textAlign: "center" }}>복기에서 찾은 패턴을 학습한 예측기가 매수·급락 순간 맞춤 알림을 띄웁니다.</p>
      <div style={{ maxWidth: 400, margin: "0 auto" }}>
        <div style={{ background: "#E9EEF3", border: "1px solid #E5E8EB", borderRadius: 28, padding: "16px 12px 22px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 7, marginBottom: 12 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#F5500A", animation: "wlpulse 1.4s ease infinite" }} />
            <span style={{ fontSize: 12, color: "#0B2E59", fontWeight: 600 }}>실시간 모니터링 중</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: "0 4px" }}>
            {alerts.length === 0 && <div style={{ textAlign: "center", color: "#8B95A1", fontSize: 14, padding: "30px 0" }}>이 사용자에 대한 실시간 알림이 없어요.</div>}
            {alerts.map((a, i) => {
              const color = DOMAIN[a.type].color; const high = (a.level || "") === "high" || a.risk >= 80;
              return (
                <div key={i} style={{ background: "#fff", borderRadius: 18, padding: 14, borderLeft: "4px solid " + color, boxShadow: "0 4px 16px rgba(0,0,0,.07)", animation: "wlslidein .45s ease both" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 9 }}>
                    <div style={{ width: 22, height: 22, borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center", background: "#F5500A" }}>
                      <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round"><polyline points="3 7 9 13 13 9 21 17" /><polyline points="21 12 21 17 16 17" /></svg>
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 600 }}>왜 잃었지?</span>
                    <span style={{ fontSize: 12.5, color, fontWeight: 500 }}>· {a.kind}</span>
                  </div>
                  <div style={{ fontSize: 15.5, fontWeight: 700, lineHeight: 1.45, marginBottom: 5 }}>{a.title}</div>
                  <div style={{ fontSize: 14, lineHeight: 1.6, color: "#4E5968" }}>{a.body}</div>
                  <div style={{ marginTop: 11 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                      <span style={{ fontSize: 11.5, color: "#8B95A1" }}>위험도</span>
                      <div style={{ flex: 1, height: 6, borderRadius: 4, background: "#EEF1F4", overflow: "hidden" }}><div style={{ width: a.risk + "%", height: "100%", background: high ? "#F5500A" : "#0B2E59" }} /></div>
                      <span style={{ fontSize: 12, fontWeight: 700, color: high ? "#F5500A" : "#0B2E59" }}>{a.risk}</span>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                      {a.reasons.map((r, k) => <span key={k} style={{ fontSize: 11, color: "#4E5968", background: "#F2F4F6", borderRadius: 5, padding: "3px 7px" }}>{r}</span>)}
                    </div>
                  </div>
                  {a.basis && <div style={{ display: "flex", gap: 6, marginTop: 10, paddingTop: 9, borderTop: "1px solid #F2F4F6", fontSize: 12.5, color: "#8B95A1", lineHeight: 1.5 }}>{a.basis}</div>}
                </div>
              );
            })}
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
  if (n == null) return "—";
  const a = Math.abs(n);
  if (a >= 1e8) return (n / 1e8).toFixed(a >= 1e9 ? 0 : 1).replace(/\.0$/, "") + "억원";
  if (a >= 1e4) return Math.round(n / 1e4).toLocaleString() + "만원";
  return Math.round(n).toLocaleString() + "원";
}

const lbl: CSSProperties = { display: "block", fontSize: 14, color: "#8B95A1", margin: "0 0 7px", fontWeight: 500 };
const inp: CSSProperties = { width: "100%", background: "#F2F4F6", border: "1px solid transparent", borderRadius: 12, padding: "15px 16px", fontSize: 16, color: "#191F28" };
const primaryBtn: CSSProperties = { width: "100%", background: "#F5500A", color: "#fff", border: "none", borderRadius: 14, padding: 16, fontSize: 16, fontWeight: 600, cursor: "pointer" };
