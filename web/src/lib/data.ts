import all from "@/data/all.json";
import revenge from "@/data/revenge.json";
import overtrading from "@/data/overtrading.json";
import disposition from "@/data/disposition.json";
import type { Report } from "./types";

// 빌드 타임에 정적으로 포함되는 에이전트 실제 출력 (psych_agent.export_web)
export const REPORTS: Record<string, Report> = {
  all: all as unknown as Report,
  revenge: revenge as unknown as Report,
  overtrading: overtrading as unknown as Report,
  disposition: disposition as unknown as Report,
};

export const SCENARIO_ORDER: { key: string; label: string }[] = [
  { key: "all", label: "혼합" },
  { key: "revenge", label: "리벤지" },
  { key: "overtrading", label: "과매매" },
  { key: "disposition", label: "처분효과" },
];
