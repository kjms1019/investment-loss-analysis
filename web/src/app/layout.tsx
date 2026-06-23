import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "왜 잃었지? — 심리·과매매 복기",
  description:
    "완결 거래내역을 사후 복기해 리벤지·과매매·처분효과를 진단하는 멀티에이전트 데모",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
