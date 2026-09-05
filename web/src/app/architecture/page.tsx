"use client";

// 발표용 아키텍처 실시간 트래킹 페이지 (단독 창).
// 실제 화면은 ArchPanel 이 그린다. 데모 화면 우측 패널과 같은 컴포넌트라
// 둘이 어긋날 일이 없다.

import ArchPanel from "@/components/ArchPanel";

export default function ArchitecturePage() {
  return <ArchPanel variant="page" />;
}
