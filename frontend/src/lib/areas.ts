import type { AreaKey } from "./types";

export const AREAS: { key: AreaKey; label: string; desc: string; color: string }[] = [
  { key: "bm", label: "Business Model", desc: "제품 · 수익구조 · 고객 · 채널", color: "var(--c-bm)" },
  { key: "growth", label: "Growth", desc: "매출 성장 · 해외 확장 · 신규사업", color: "var(--c-growth)" },
  { key: "risk", label: "Risk", desc: "거래처 집중 · 규제 · 경쟁구조", color: "var(--c-risk)" },
  { key: "fin", label: "Finance", desc: "수익성 · 안정성 · 현금흐름", color: "var(--c-fin)" },
];
export const AREA_KEYS: AreaKey[] = ["bm", "growth", "risk", "fin"];
