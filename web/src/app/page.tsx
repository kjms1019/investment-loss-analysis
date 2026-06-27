"use client";

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import {
  api, type Alert, type Dashboard, type Pattern, type Trade, type UserItem, type DomainId,
} from "@/lib/api";
import { DOMAIN, SEV_LABEL, DomainIcon, Logo, Section, LossBars } from "@/components/why/ui";

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
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [err, setErr] = useState<string>("");

  const [filterType, setFilterType] = useState<DomainId | "all">("all");
  const [filterSev, setFilterSev] = useState<string>("all");
  const [consentAgreed, setConsentAgreed] = useState(false);
  const [progressStep, setProgressStep] = useState(0);
  const [analyzeDone, setAnalyzeDone] = useState(false);
  const [selTrade, setSelTrade] = useState<number | null>(null);

  // 해시 라우팅
  useEffect(() => {
    const sync = () => {
      const id = (window.location.hash || "").replace(/^#\/?/, "") as Screen;
      setScreen(ROUTES.includes(id) ? id : "login");
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
    api.dashboard(u).then(setDash).catch((e) => { setDash(null); setErr(String(e)); });
    api.trades(u).then((d) => setTrades(d.trades)).catch(() => setTrades([]));
    api.profile(u).then((d) => setPatterns(d.patterns)).catch(() => setPatterns([]));
    api.alerts(u).then((d) => setAlerts(d.alerts)).catch(() => setAlerts([]));
  }, []);
  useEffect(() => { loadUser(user); }, [user, loadUser]);

  // 분석 진행 애니메이션
  useEffect(() => {
    if (screen !== "analyze") return;
    setProgressStep(0); setAnalyzeDone(false);
    const STEP_MS = 1500; // 사람이 단계 문구를 읽을 시간 확보
    const ts = [1, 2, 3].map((n) => setTimeout(() => setProgressStep(n), STEP_MS * n));
    ts.push(setTimeout(() => { setProgressStep(4); setAnalyzeDone(true); }, STEP_MS * 4));
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

        {screen === "login" && <Login onLogin={() => go("consent")} onDemo={() => { if (users[0]) setUser(users[0].id); go("consent"); }} />}
        {screen === "consent" && <Consent agreed={consentAgreed} toggle={() => setConsentAgreed((v) => !v)} onBack={() => go("login")} onStart={() => go("upload")} />}
        {screen === "upload" && <Upload users={users} user={user} setUser={setUser} onStart={() => go("analyze")} />}
        {screen === "analyze" && <Analyze step={progressStep} done={analyzeDone} trades={trades} onGo={() => go("dashboard")} />}
        {screen === "dashboard" && <DashboardView dash={dash} trades={trades} onCard={(t) => { setFilterType(t); setFilterSev("all"); go("trades"); }} />}
        {screen === "trades" && <TradesView trades={trades} filterType={filterType} setFilterType={setFilterType} filterSev={filterSev} setFilterSev={setFilterSev} selTrade={selTrade} setSelTrade={setSelTrade} />}
        {screen === "profile" && <ProfileView patterns={patterns} />}
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
  return (
    <div style={{ maxWidth: 400, margin: "0 auto", padding: "48px 2px 40px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 40 }}><Logo size={34} /><div style={{ fontWeight: 700, fontSize: 18 }}>왜 잃었지?</div></div>
      <h1 style={{ fontSize: 26, fontWeight: 700, color: "#0B2E59", lineHeight: 1.34, margin: "0 0 10px" }}>내 거래 복기를<br />이어서 확인해 볼까요?</h1>
      <p style={{ color: "#8B95A1", fontSize: 16, lineHeight: 1.6, margin: "0 0 32px" }}>로그인하면 지난 진단 결과와 실시간 알림을 그대로 이어볼 수 있어요.</p>
      <label style={lbl}>휴대폰 번호</label>
      <input placeholder="010-0000-0000" style={inp} />
      <label style={{ ...lbl, marginTop: 16 }}>비밀번호</label>
      <input type="password" placeholder="비밀번호 입력" style={inp} />
      <button onClick={onLogin} style={{ ...primaryBtn, marginTop: 24 }}>로그인</button>
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
      <button onClick={() => agreed && onStart()} style={{ width: "100%", border: "none", borderRadius: 14, padding: 16, fontSize: 16, fontWeight: 600, cursor: agreed ? "pointer" : "default", background: agreed ? "#F5500A" : "#E5E8EB", color: agreed ? "#fff" : "#B0B8C1" }}>동의하고 시작하기</button>
      <button onClick={onStart} style={{ width: "100%", background: "none", border: "none", color: "#8B95A1", fontSize: 15.5, fontWeight: 500, padding: 16, cursor: "pointer", marginTop: 4 }}>다음에 하기</button>
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
function Analyze({ step, done, trades, onGo }: {
  step: number; done: boolean; trades: Trade[]; onGo: () => void;
}) {
  // 선택은 도메인이 아니라 '카드(축)' 단위 — 두 카드가 같은 도메인일 수 있어서.
  const [pick, setPick] = useState<"freq" | "amount" | null>(null);
  useEffect(() => { if (!done) setPick(null); }, [done]);

  // 전체 거래 차트 — 단계가 진행될수록 '색인'이 점진적으로 들어간다.
  //  step≤1(파싱): 전체 거래 무색  → step2(손실 선별): 손실만 진하게  → step≥3(라우팅): 도메인 색.
  const stage = step <= 1 ? "all" : step === 2 ? "loss" : "routed";
  const chartBars = trades.map((t) => {
    const v = -(t.loss ?? t.score ?? 1);
    if (stage === "all") return { v, color: "#C4CDD5", dim: true };
    if (stage === "loss") return { v, color: "#9FB1CC", dim: false };
    return { v, color: DOMAIN[t.type].color, dim: false };
  });
  const stageNote = stage === "all" ? "전체 거래를 불러왔어요" : stage === "loss" ? "‘당신 탓’ 손실만 골라내는 중…" : "진입오류·손절실패로 분류하는 중…";
  const chart = chartBars.length > 0 ? (
    <div style={{ background: "#F8F9FA", border: "1px solid #F2F4F6", borderRadius: 16, padding: "18px 18px 16px", marginBottom: 22 }}>
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
        <div style={{ fontSize: 14.5, fontWeight: 600 }}>최근 거래 {chartBars.length}건<span style={{ color: "#8B95A1", fontWeight: 400, fontSize: 13, marginLeft: 8 }}>막대 1개 = 거래 1건 · {stageNote}</span></div>
        <div style={{ display: "flex", gap: 12, marginLeft: "auto", fontSize: 12, color: "#8B95A1" }}>
          <Legend color="#ECEEF0" label="전체(이익)" /><Legend color={DOMAIN.entry.color} label="진입오류" /><Legend color={DOMAIN.cut.color} label="손절실패" />
        </div>
      </div>
      <LossBars values={chartBars} height={150} />
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
                  <div style={{ fontSize: 12, color: o.primary === "빈도" ? m.color : "#8B95A1", marginBottom: 3, fontWeight: o.primary === "빈도" ? 600 : 400 }}>빈도</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "#191F28" }}>{st.count}<span style={{ fontSize: 12.5, color: "#8B95A1", fontWeight: 500, marginLeft: 2 }}>건</span></div>
                </div>
                <div style={{ width: 1, background: "#E5E8EB" }} />
                <div>
                  <div style={{ fontSize: 12, color: o.primary === "총손실금" ? m.color : "#8B95A1", marginBottom: 3, fontWeight: o.primary === "총손실금" ? 600 : 400 }}>총 손실금</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: m.color }}>{won(st.amount)}</div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <button onClick={() => selType && onGo()} disabled={!selType}
        style={{ ...primaryBtn, marginTop: 22, background: selType ? "#F5500A" : "#E5E8EB", color: selType ? "#fff" : "#B0B8C1", cursor: selType ? "pointer" : "default" }}>
        {selType ? `‘${DOMAIN[selType].name}’ 진단 결과 보기 →` : "둘 중 하나를 선택해 주세요"}
      </button>
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
function DashboardView({ dash, trades, onCard }: { dash: Dashboard | null; trades: Trade[]; onCard: (t: DomainId) => void }) {
  if (!dash) return <Loading />;
  const bars = trades.map((t) => ({ v: t.score ?? 1, color: DOMAIN[t.type].color }));
  return (
    <div>
      <Section step="3" label="복기 루프 · 3단계 진단 대시보드" />
      <h2 style={{ fontSize: "clamp(24px,4.2vw,36px)", fontWeight: 700, color: "#0B2E59", lineHeight: 1.3, margin: "14px 0 12px" }}>당신의 1순위 문제는<br /><span>{dash.dominant.name}</span>입니다.</h2>
      <p style={{ color: "#8B95A1", fontSize: 16, lineHeight: 1.65, margin: "0 0 26px", maxWidth: 620 }}>본인 탓 손실 <b style={{ color: "#191F28" }}>{dash.total_loss_trades}건</b> 중 가장 큰 덩어리예요. 비난이 아니라, 여기서부터 바꿔보자는 신호예요.</p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 13, marginBottom: 22 }}>
        <Stat label="본인 탓 손실 거래" value={`${dash.total_loss_trades}`} unit="건" />
        <Stat label="손절실패" value={`${dash.counts.cut}`} unit="건" />
        <Stat label="진입오류" value={`${dash.counts.entry}`} unit="건" />
      </div>

      {trades.length > 0 && (
        <div style={{ background: "#F8F9FA", border: "1px solid #F2F4F6", borderRadius: 16, padding: "18px 18px 16px", marginBottom: 22 }}>
          <div style={{ fontSize: 14.5, fontWeight: 600, marginBottom: 16 }}>손실 거래 {trades.length}건 · 위험점수 크기</div>
          <LossBars values={bars} height={150} />
        </div>
      )}

      <div style={{ background: "#F2F4F6", borderRadius: 14, padding: "20px 20px 22px", marginBottom: 14 }}>
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 20 }}>손실 도메인 분포<span style={{ color: "#8B95A1", fontWeight: 400, fontSize: 13.5, marginLeft: 8 }}>총 {dash.total_loss_trades}건</span></div>
        {dash.dist.map((d) => {
          const max = Math.max(1, ...dash.dist.map((x) => x.count));
          return (
            <div key={d.id} style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 9 }}>
                <DomainIcon type={d.id} size={18} />
                <div style={{ fontSize: 15, fontWeight: 600 }}>{d.name}</div>
                <div style={{ marginLeft: "auto", fontSize: 14.5, color: "#8B95A1" }}><b style={{ color: "#191F28" }}>{d.count}</b>건</div>
              </div>
              <div style={{ height: 12, background: "#E9ECEF", borderRadius: 7, overflow: "hidden" }}>
                <div style={{ height: "100%", background: d.color, width: `${Math.round((d.count / max) * 100)}%` }} />
              </div>
              <div style={{ fontSize: 12, color: "#8B95A1", marginTop: 8 }}>{d.psych} 흡수 심리</div>
            </div>
          );
        })}
      </div>

      <div style={{ fontSize: 14, color: "#8B95A1", margin: "14px 0 11px" }}>도메인 카드를 누르면 해당 거래만 모아 볼 수 있어요.</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 13 }}>
        {dash.typeCards.map((c) => (
          <button key={c.id} onClick={() => onCard(c.id)} style={{ textAlign: "left", cursor: "pointer", background: "#fff", border: "1px solid #E5E8EB", borderTop: "3px solid " + c.color, borderRadius: 14, padding: 18 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ width: 38, height: 38, borderRadius: 11, display: "flex", alignItems: "center", justifyContent: "center", background: c.tint }}><DomainIcon type={c.id} size={20} /></div>
              <div style={{ fontSize: 26, fontWeight: 700, color: c.color }}>{c.count}<span style={{ fontSize: 14, color: "#8B95A1", marginLeft: 2, fontWeight: 500 }}>건</span></div>
            </div>
            <div style={{ fontSize: 15.5, fontWeight: 700, marginTop: 14 }}>{c.name}</div>
            <div style={{ fontSize: 13.5, color: "#8B95A1", marginTop: 4, lineHeight: 1.5 }}>“{c.def}”</div>
            <div style={{ display: "inline-flex", marginTop: 11, padding: "4px 9px", borderRadius: 7, background: c.tint }}><span style={{ fontSize: 12.5, color: c.color, fontWeight: 600 }}>{c.psychLabel}</span></div>
            <div style={{ fontSize: 13.5, color: c.color, marginTop: 12, fontWeight: 500 }}>거래 보기 →</div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ── ④ TRADES ─────────────────────────────────────────────────────────────────
const SIG_W: Record<string, number> = { 확대: 0.35, 지연: 0.3, 물타기: 0.2 };
function TradesView({ trades, filterType, setFilterType, filterSev, setFilterSev, selTrade, setSelTrade }: {
  trades: Trade[]; filterType: DomainId | "all"; setFilterType: (t: DomainId | "all") => void;
  filterSev: string; setFilterSev: (s: string) => void; selTrade: number | null; setSelTrade: (n: number | null) => void;
}) {
  const filtered = trades.filter((t) => (filterType === "all" || t.type === filterType) && (filterSev === "all" || t.sev === filterSev));
  return (
    <div>
      <Section step="4" label="복기 루프 · 4단계 거래별 설명" />
      <h2 style={{ fontSize: "clamp(22px,3.6vw,28px)", fontWeight: 700, color: "#0B2E59", margin: "14px 0 8px" }}>거래마다, 왜 잃었는지</h2>
      <p style={{ color: "#8B95A1", fontSize: 16, margin: "0 0 20px" }}>손실 거래 하나하나에 원인을 정리했어요. 도메인·심각도로 추려 보세요.</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 10 }}>
        {([["all", "전체"], ["cut", "손절실패"], ["entry", "진입오류"]] as const).map(([id, label]) => {
          const active = filterType === id; const col = id === "all" ? "#0B2E59" : DOMAIN[id as DomainId].color;
          return <button key={id} onClick={() => { setFilterType(id); setSelTrade(null); }} style={{ cursor: "pointer", fontSize: 13.5, borderRadius: 9, padding: "8px 15px", fontWeight: active ? 600 : 500, background: active ? col : "#F2F4F6", color: active ? "#fff" : "#8B95A1", border: "none" }}>{label}</button>;
        })}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 20 }}>
        {([["all", "전체 심각도"], ["strong", "강함"], ["moderate", "보통"], ["weak", "약함"]] as const).map(([id, label]) => {
          const active = filterSev === id;
          return <button key={id} onClick={() => { setFilterSev(id); setSelTrade(null); }} style={{ cursor: "pointer", fontSize: 13, borderRadius: 9, padding: "7px 13px", fontWeight: 500, background: active ? "#E8EBED" : "transparent", color: active ? "#191F28" : "#8B95A1", border: "1px solid " + (active ? "transparent" : "#E5E8EB") }}>{label}</button>;
        })}
      </div>
      <div style={{ fontSize: 13.5, color: "#8B95A1", marginBottom: 14 }}>{filtered.length}건</div>
      {filtered.length === 0 && <div style={{ textAlign: "center", padding: "50px 20px", color: "#8B95A1", fontSize: 15, background: "#F2F4F6", borderRadius: 14 }}>해당하는 거래가 없어요. 필터를 바꿔보세요.</div>}
      <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
        {filtered.map((t, i) => {
          const m = DOMAIN[t.type]; const sel = selTrade === i;
          const eW = Math.round((t.eScore ?? 0) * 100), cW = Math.round((t.cScore ?? 0) * 100);
          return (
            <div key={t.trade_id} onClick={() => setSelTrade(i)} style={{ cursor: "pointer", background: "#fff", borderTop: "1px solid " + (sel ? m.color : "#E5E8EB"), borderRight: "1px solid " + (sel ? m.color : "#E5E8EB"), borderBottom: "1px solid " + (sel ? m.color : "#E5E8EB"), borderLeft: "3px solid " + m.color, borderRadius: 14, padding: "17px 18px", boxShadow: sel ? "0 0 0 2px " + m.tint : "none" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 10px 5px 8px", borderRadius: 8, background: m.tint }}>
                  <DomainIcon type={t.type} size={15} /><span style={{ fontSize: 13.5, fontWeight: 600, color: m.color }}>{t.typeName}</span>
                </div>
                <span style={{ fontSize: 11.5, fontWeight: 600, borderRadius: 6, padding: "4px 9px", color: "#8B95A1", background: "#F2F4F6" }}>{SEV_LABEL[t.sev] || t.sev}</span>
                {t.label && <span style={{ fontSize: 11.5, fontWeight: 600, borderRadius: 6, padding: "4px 9px", color: m.color, background: m.tint }}>{t.label}</span>}
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap", margin: "14px 0 2px" }}>
                <span style={{ fontSize: 17, fontWeight: 700 }}>{t.name || t.code}</span>
                <span style={{ fontSize: 13.5, color: "#8B95A1" }}>{t.code}</span>
                <span style={{ fontSize: 13.5, color: "#8B95A1", marginLeft: "auto" }}>진입 {t.date}</span>
              </div>
              {(t.eScore != null && t.cScore != null) && (
                <div style={{ background: "#F8F9FA", borderRadius: 10, padding: "11px 12px", margin: "10px 0 13px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                    <span style={{ fontSize: 12.5, color: "#8B95A1" }}>분류기 라우팅 점수</span>
                    <span style={{ fontSize: 11.5, fontWeight: 600, borderRadius: 6, padding: "3px 8px", color: "#0B2E59", background: "#EAF0F8" }}>{t.route || "—"} · 신뢰도 {t.conf != null ? Math.round(t.conf * 100) + "%" : "—"}</span>
                  </div>
                  <div style={{ display: "flex", height: 8, borderRadius: 5, overflow: "hidden", background: "#E9ECEF" }}>
                    <div style={{ width: eW + "%", background: "#F0890C" }} /><div style={{ width: cW + "%", background: "#0B2E59" }} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 11.5, color: "#8B95A1" }}>
                    <span>진입오류 {t.eScore?.toFixed(2)}</span><span>손절실패 {t.cScore?.toFixed(2)}</span>
                  </div>
                </div>
              )}
              <p style={{ fontSize: 15, lineHeight: 1.7, color: "#4E5968", margin: "0 0 13px" }}>{t.desc}</p>
              {t.signals && (
                <div style={{ display: "flex", gap: 6, marginBottom: 4 }}>
                  {Object.entries(t.signals).map(([k, v]) => {
                    const on = (v ?? 0) > 0.05;
                    return (
                      <div key={k} style={{ flex: "1 1 0", textAlign: "center", borderRadius: 9, padding: "9px 4px", background: on ? "#E7ECF4" : "#F2F4F6", border: "1px solid " + (on ? "#0B2E59" : "transparent") }}>
                        <div style={{ fontSize: 12.5, fontWeight: 600, color: on ? "#0B2E59" : "#B0B8C1" }}>{k}</div>
                        <div style={{ fontSize: 11, color: "#8B95A1", marginTop: 2 }}>{(v ?? 0).toFixed(2)} <span style={{ color: "#C4CDD5" }}>·w{SIG_W[k]}</span></div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── ⑤ PROFILE ────────────────────────────────────────────────────────────────
function ProfileView({ patterns }: { patterns: Pattern[] }) {
  return (
    <div>
      <Section step="5" label="복기 루프 · 5단계 내 성향 프로파일" />
      <h2 style={{ fontSize: "clamp(22px,3.8vw,30px)", fontWeight: 700, color: "#0B2E59", lineHeight: 1.32, margin: "14px 0 12px" }}>당신은 이런 패턴을<br />반복하고 있어요</h2>
      <p style={{ color: "#8B95A1", fontSize: 16, lineHeight: 1.7, margin: "0 0 14px", maxWidth: 640 }}>다음 거래에서 딱 한 가지만 바꿔보자는 거예요.</p>
      <div style={{ display: "inline-flex", alignItems: "center", gap: 7, background: "#0B2E59", borderRadius: 9, padding: "9px 13px", marginBottom: 24 }}>
        <span style={{ fontSize: 13.5, color: "#EAF0F8", fontWeight: 500 }}>이 패턴들이 곧 실시간 알림(예측기)의 학습 근거가 돼요.</span>
      </div>
      {patterns.length === 0 && <Loading />}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 13 }}>
        {patterns.map((p, i) => (
          <div key={i} style={{ background: "#fff", border: "1px solid #E5E8EB", borderRadius: 14, padding: 18 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 12 }}>
              <div style={{ width: 34, height: 34, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", background: p.tint }}><DomainIcon type={p.type} size={18} /></div>
              <div style={{ fontSize: 12.5, color: p.color, fontWeight: 600 }}>{p.typeName}</div>
            </div>
            <div style={{ fontSize: 16, fontWeight: 700, lineHeight: 1.45, marginBottom: 10 }}>{p.title}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <span style={{ fontSize: 18, fontWeight: 700, color: p.color }}>{p.stat}</span>
              <span style={{ fontSize: 12.5, color: "#8B95A1", background: "#F2F4F6", borderRadius: 5, padding: "3px 8px" }}>{p.tag}</span>
            </div>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: p.tint, borderRadius: 10, padding: "12px 13px" }}>
              <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke={p.color} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" style={{ flex: "0 0 auto", marginTop: 2 }}><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>
              <div style={{ fontSize: 14, lineHeight: 1.6, color: "#4E5968" }}>{p.correction}</div>
            </div>
          </div>
        ))}
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
