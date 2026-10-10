import { describe, expect, it } from "vitest";
import { api } from "../api";
import { applyWeights, computeBand, DEFAULT_LEVELS, defaultSelection, toPercents } from "../lib/scoring";

describe("영역 중요도 → 비중", () => {
  it("기본 2/3/1/4 → 20/30/10/40%", () => {
    const p = toPercents(DEFAULT_LEVELS);
    expect([p.bm, p.growth, p.risk, p.fin].map(Math.round)).toEqual([20, 30, 10, 40]);
  });
  it("합계 0이면 모두 0", () => {
    expect(toPercents({ bm: 0, growth: 0, risk: 0, fin: 0 })).toEqual({ bm: 0, growth: 0, risk: 0, fin: 0 });
  });
});

describe("applyWeights (Late Fusion 재계산)", () => {
  it("기본 중요도에서는 서버가 준 종합 점수와 같다", async () => {
    const r = await api.getSimilar("TGT");
    const w = applyWeights(r, DEFAULT_LEVELS);
    r.items.forEach((it) => {
      const m = w.items.find((x) => x.company.id === it.company.id)!;
      expect(Math.abs(m.scores.fused - it.scores.fused)).toBeLessThan(0.3);
    });
  });
  it("Risk만 높이면 순위가 바뀔 수 있고 rank 는 1..N 으로 다시 매겨진다", async () => {
    const r = await api.getSimilar("TGT");
    const w = applyWeights(r, { bm: 0, growth: 0, risk: 4, fin: 0 });
    expect(w.items.map((i) => i.rank)).toEqual([1, 2, 3, 4, 5]);
    expect(w.items[0].company.id).toBe("P02"); // 위험 영역 점수가 가장 높은 기업
  });
  it("영역 점수가 없으면 원본 점수 유지", async () => {
    const r = await api.getSimilar("TGT");
    const bare = { ...r, items: r.items.map((i) => ({ ...i, scores: { ...i.scores, areas: null } })) };
    expect(applyWeights(bare, { bm: 4, growth: 0, risk: 0, fin: 0 }).items.map((i) => i.scores.fused)).toEqual(r.items.map((i) => i.scores.fused));
  });
});

describe("computeBand", () => {
  it("시안 예시: PER 22.4/25.8/18.6, 순이익 120억, 1,000만 주, 할인 15–25% → 20,040–22,712원", () => {
    const b = computeBand({ pers: [22.4, 25.8, 18.6], netIncomeEok: 120, baseShares: 1000, newShares: 0, discMin: 15, discMax: 25 })!;
    expect(Math.round(b.perShare)).toBe(26720);
    expect(Math.round(b.low)).toBe(20040);
    expect(Math.round(b.high)).toBe(22712);
  });
  it("신주 200만 주 반영 시 주당 평가액이 줄어든다", () => {
    const b = computeBand({ pers: [22.4, 25.8, 18.6], netIncomeEok: 120, baseShares: 1000, newShares: 200, discMin: 15, discMax: 25 })!;
    expect(Math.round(b.perShare)).toBe(22267);
    expect(Math.round(b.low)).toBe(16700);
    expect(Math.round(b.high)).toBe(18927);
  });
  it("입력이 올바르지 않으면 null", () => {
    expect(computeBand({ pers: [], netIncomeEok: 120, baseShares: 1000, newShares: 0, discMin: 15, discMax: 25 })).toBeNull();
    expect(computeBand({ pers: [20], netIncomeEok: 120, baseShares: 1000, newShares: 0, discMin: 30, discMax: 25 })).toBeNull();
    expect(computeBand({ pers: [20], netIncomeEok: null, baseShares: 1000, newShares: 0, discMin: 15, discMax: 25 })).toBeNull();
  });
  it("기본 선택은 included 이고 PER 이 있는 기업", async () => {
    expect(defaultSelection(await api.getValuation("TGT"))).toEqual(["P01", "P02", "P03"]);
  });
});
