import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "왜 잃었지? · 거래 복기 + 실시간 알림",
  description:
    "손실 원인(진입오류·손절실패)을 복기하고, 같은 실수의 순간 실시간으로 경고하는 멀티에이전트 시스템",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
