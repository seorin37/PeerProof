import type { AreaKey, SimilarCompany, SimilarResult, Valuation } from "../types/domain";

export const AREAS: { key: AreaKey; label: string; hint: string; color: string }[] = [
  { key: "bm", label: "Business Model", hint: "제품 · 수익구조 · 고객 · 채널", color: "var(--c-bm)" },
  { key: "growth", label: "Growth", hint: "매출 성장 · 해외 확장 · 신규사업", color: "var(--c-growth)" },
  { key: "risk", label: "Risk", hint: "거래처 집중 · 규제 · 경쟁구조", color: "var(--c-risk)" },
  { key: "fin", label: "Finance", hint: "수익성 · 안정성 · 현금흐름", color: "var(--c-fin)" },
];
export const LEVEL_LABELS = ["없음", "낮음", "중간", "높음", "매우 높음"];

export type Levels = Record<AreaKey, number>;
export const DEFAULT_LEVELS: Levels = { bm: 2, growth: 3, risk: 1, fin: 4 };

export const levelSum = (l: Levels) => l.bm + l.growth + l.risk + l.fin;

/** 0–4 단계 중요도를 합계로 나눈 비중(%). 합계가 0이면 모두 0 */
export function toPercents(l: Levels): Levels {
  const s = levelSum(l);
  const f = (n: number) => (s === 0 ? 0 : (n / s) * 100);
  return { bm: f(l.bm), growth: f(l.growth), risk: f(l.risk), fin: f(l.fin) };
}

/**
 * 영역 중요도를 임베딩 유사도에 반영하고 Late Fusion 으로 종합유사도를 다시 계산합니다.
 *  임베딩 = Σ(영역 점수 × 영역 비중),  종합 = 임베딩 × w_emb + 네트워크 × w_net
 * 영역 점수나 fusion 가중치가 없으면 서버가 준 점수를 그대로 사용합니다.
 * (백엔드가 가중치를 직접 받도록 바뀌면 이 함수만 교체하면 됩니다.)
 */
export function applyWeights(r: SimilarResult, levels: Levels): SimilarResult {
  const p = toPercents(levels);
  const total = levelSum(levels);
  const items: SimilarCompany[] = r.items.map((it) => {
    const a = it.scores.areas;
    if (!a || total === 0) return it;
    const emb = (a.bm * p.bm + a.growth * p.growth + a.risk * p.risk + a.fin * p.fin) / 100;
    const net = it.scores.network;
    const fused = r.fusion && net !== null ? emb * r.fusion.embeddingWeight + net * r.fusion.networkWeight : emb;
    return { ...it, scores: { ...it.scores, embedding: emb, fused } };
  });
  items.sort((x, y) => y.scores.fused - x.scores.fused);
  return { ...r, items: items.map((it, i) => ({ ...it, rank: i + 1 })) };
}

export const canWeigh = (r: SimilarResult) => r.items.some((i) => !!i.scores.areas);

/** 화면에서 직접 고르기 전 기본 선택: 백엔드가 included 로 표시하고 PER 이 있는 기업 */
export function defaultSelection(v: Valuation | null): string[] {
  return v ? v.peers.filter((p) => p.included && p.per !== null).map((p) => p.companyId) : [];
}

export const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
export function median(xs: number[]) {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export interface BandInput {
  pers: number[];
  netIncomeEok: number | null; // 억원
  baseShares: number | null; // 만주
  newShares: number; // 만주
  discMin: number; // %
  discMax: number; // %
}
export interface Band {
  avgPer: number;
  medianPer: number;
  equityEok: number;
  totalShares: number;
  perShare: number;
  low: number;
  high: number;
}

/** 지분가치 = 평균 PER × 순이익,  주당 평가액 = 지분가치 ÷ 적용 주식수,  밴드 = 주당 × (1 − 할인율) */
export function computeBand(i: BandInput): Band | null {
  const avg = mean(i.pers);
  const med = median(i.pers);
  if (avg === null || med === null || i.netIncomeEok === null || i.baseShares === null) return null;
  const totalShares = i.baseShares + i.newShares;
  if (!(totalShares > 0) || !(i.netIncomeEok > 0)) return null;
  if (i.discMin < 0 || i.discMax > 100 || i.discMin > i.discMax) return null;
  const equityEok = avg * i.netIncomeEok;
  const perShare = (equityEok / totalShares) * 1e4;
  return { avgPer: avg, medianPer: med, equityEok, totalShares, perShare, low: perShare * (1 - i.discMax / 100), high: perShare * (1 - i.discMin / 100) };
}
