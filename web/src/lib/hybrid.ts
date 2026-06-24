import hybridAll from "@/data/hybrid_all.json";
import hybridRevenge from "@/data/hybrid_revenge.json";
import hybridDisposition from "@/data/hybrid_disposition.json";
import type { HybridReport } from "./types";

export const HYBRIDS: Record<string, HybridReport> = {
  all: hybridAll as unknown as HybridReport,
  revenge: hybridRevenge as unknown as HybridReport,
  disposition: hybridDisposition as unknown as HybridReport,
};

export const HYBRID_SCENARIOS: { key: string; label: string }[] = [
  { key: "all", label: "혼합" },
  { key: "revenge", label: "리벤지 중심" },
  { key: "disposition", label: "처분효과 중심" },
];
