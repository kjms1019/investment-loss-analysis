// 데모 페이지 ↔ /architecture 페이지 실시간 연동 채널.
// 데모에서 단계/버튼이 바뀔 때 archSet(...)으로 "지금 활성 노드"를 broadcast 하면,
// 같은 출처(localhost:3000)의 아키텍처 페이지가 받아 해당 노드를 하이라이트한다.
//
// 전달 경로 2개(견고성): BroadcastChannel(같은 출처 탭 즉시) + localStorage(새 탭 초기 동기화·폴백).

export type ArchMsg = { nodes: string[]; note?: string; t?: number };

const KEY = "mirae-arch";
export const ARCH_KEY = KEY;

let ch: BroadcastChannel | null = null;
function chan(): BroadcastChannel | null {
  if (typeof window === "undefined") return null;
  if (!ch && "BroadcastChannel" in window) ch = new BroadcastChannel(KEY);
  return ch;
}

/** 데모 측에서 호출: 지금 켜져야 할 아키텍처 노드 id 목록 + 설명. */
export function archSet(nodes: string[], note?: string): void {
  if (typeof window === "undefined") return;
  const msg: ArchMsg = { nodes, note, t: Date.now() };
  try { chan()?.postMessage(msg); } catch { /* noop */ }
  try { localStorage.setItem(KEY, JSON.stringify(msg)); } catch { /* noop */ }
}

/** 아키텍처 페이지 측에서 호출: 메시지 구독. 마운트 시 localStorage의 마지막 상태도 1회 전달. */
export function archSubscribe(cb: (m: ArchMsg) => void): () => void {
  if (typeof window === "undefined") return () => {};
  const c = chan();
  const onMsg = (e: MessageEvent) => cb(e.data as ArchMsg);
  c?.addEventListener("message", onMsg);
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY && e.newValue) { try { cb(JSON.parse(e.newValue) as ArchMsg); } catch { /* noop */ } }
  };
  window.addEventListener("storage", onStorage);
  try { const raw = localStorage.getItem(KEY); if (raw) cb(JSON.parse(raw) as ArchMsg); } catch { /* noop */ }
  return () => {
    c?.removeEventListener("message", onMsg);
    window.removeEventListener("storage", onStorage);
  };
}
