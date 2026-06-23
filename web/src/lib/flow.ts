import flowAll from "@/data/flow_all.json";
import flowRevenge from "@/data/flow_revenge.json";
import flowOver from "@/data/flow_overtrading.json";
import flowDisp from "@/data/flow_disposition.json";
import type { Flow, PsychType } from "./types";

// 파이프라인(손실선별 → 심리 귀속) 실제 출력. web_export 가 생성.
export const FLOWS: Record<string, Flow> = {
  all: flowAll as unknown as Flow,
  revenge: flowRevenge as unknown as Flow,
  overtrading: flowOver as unknown as Flow,
  disposition: flowDisp as unknown as Flow,
};

export const TYPE_META: Record<
  PsychType | "other",
  { label: string; text: string; bg: string; ring: string; bar: string }
> = {
  revenge: { label: "리벤지", text: "text-rose-300", bg: "bg-rose-500/10", ring: "ring-rose-500/30", bar: "bg-rose-400" },
  overtrading: { label: "과매매", text: "text-amber-300", bg: "bg-amber-500/10", ring: "ring-amber-500/30", bar: "bg-amber-400" },
  disposition: { label: "처분효과", text: "text-violet-300", bg: "bg-violet-500/10", ring: "ring-violet-500/30", bar: "bg-violet-400" },
  other: { label: "기타(비심리)", text: "text-slate-400", bg: "bg-slate-500/10", ring: "ring-slate-600/30", bar: "bg-slate-600" },
};
