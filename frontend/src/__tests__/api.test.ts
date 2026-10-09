import { describe, expect, it } from "vitest";
import { api } from "../api";
import { adaptMetrics, adaptNetwork, adaptSimilar } from "../api/adapters";
import { ApiError } from "../api/errors";
import { circularLayout, deriveStats, sharedLabels } from "../lib/network";

describe("mock API → domain", () => {
  it("검색: 이름으로 필터링", async () => {
    const all = await api.searchCompanies("");
    expect(all.length).toBeGreaterThan(1);
    const one = await api.searchCompanies("예시시큐어");
    expect(one.map((c) => c.name)).toEqual(["예시시큐어"]);
  });
  it("유사기업 Top 5, 점수는 0–100, 순위순", async () => {
    const r = await api.getSimilar("TGT");
    expect(r.items).toHaveLength(5);
    r.items.forEach((x, i) => {
      expect(x.rank).toBe(i + 1);
      expect(x.scores.fused).toBeGreaterThan(1);
      expect(x.scores.fused).toBeLessThanOrEqual(100);
    });
  });
  it("프로필: 근거 없는 값은 미확인", async () => {
    const p = await api.getProfile("TGT");
    expect(p.sections.length).toBe(4);
    expect(p.sections.flatMap((s) => s.items).some((i) => i.value === "미확인")).toBe(true);
  });
  it("재무 지표: 대상기업이 첫 행, 비율은 %로 변환, 계산 불가는 null", async () => {
    const m = await api.getMetrics("TGT");
    expect(m.rows[0].isTarget).toBe(true);
    expect(m.rows.filter((r) => r.isTarget)).toHaveLength(1);
    expect(m.rows[0].values.revenue_growth_rate).toBeCloseTo(38, 5);
    expect(m.rows.some((r) => r.values.overseas_revenue_ratio === null)).toBe(true);
  });
  it("네트워크/설명 응답", async () => {
    const n = await api.getNetwork("P01");
    expect(n.nodes.length).toBeGreaterThan(3);
    const e = await api.getExplanation("TGT", "P01");
    expect(e.summary).not.toMatch(/\{target\}|\{peer\}/);
  });
});

describe("adapters 방어", () => {
  it("필수 필드 누락 → shape 오류", () => {
    expect(() => adaptSimilar({ foo: 1 })).toThrow(ApiError);
    expect(() => adaptMetrics(null)).toThrow(ApiError);
  });
  it("존재하지 않는 노드를 가리키는 간선은 제거", () => {
    const n = adaptNetwork({ company_id: "A", nodes: [{ id: "1", label: "a", centrality: 0.5 }], edges: [{ source: "1", target: "9", weight: 1 }] });
    expect(n.edges).toHaveLength(0);
  });
});

describe("network utils", () => {
  const net = (labels: string[]) => ({ companyId: "x", nodes: labels.map((l, i) => ({ id: String(i), label: l, centrality: 0.5 })), edges: [] });
  it("공통 키워드", () => {
    expect([...sharedLabels(net(["a", "b"]), net(["B", "c"]))]).toEqual(["b"]);
  });
  it("레이아웃은 모든 노드 좌표 제공", () => {
    expect(circularLayout(net(["a", "b", "c"]), 600, 400, 50).size).toBe(3);
  });
  it("deriveStats", () => {
    expect(deriveStats([20, 21, 26])).toEqual({ min: 20, median: 21, max: 26 });
    expect(deriveStats([])).toBeNull();
  });
});
