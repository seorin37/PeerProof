/**
 * 백엔드 계약 테스트: build_serving_data.py 가 만든 실제 JSON 을 어댑터로 읽어 본다.
 * 실행:  PEERPROOF_SERVING_DIR=<data/serving 경로> npx vitest run contract
 * 환경변수가 없으면 건너뜁니다(mock 기반 기본 테스트에는 영향 없음).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import type { CompanySummary } from "../types/domain";
import { adaptCompanies, adaptMetrics, adaptNetwork, adaptProfile, adaptSimilar } from "../api/adapters";

const DIR = process.env.PEERPROOF_SERVING_DIR;
const read = (...p: string[]) => JSON.parse(readFileSync(join(DIR as string, ...p), "utf-8"));

describe.skipIf(!DIR)("서빙 JSON → 어댑터", () => {
  let companies: CompanySummary[] = [];
  let targetId = "";
  beforeAll(() => {
    companies = adaptCompanies(read("companies.json"));
    targetId = companies[0]?.id ?? "";
  });

  it("companies.json: 회사 목록", () => {
    expect(companies.length).toBeGreaterThan(0);
    companies.forEach((c) => expect(c.name).toBeTruthy());
  });

  it("회사마다 profile.json 이 있고 근거 id 가 모두 연결된다", () => {
    companies.forEach((c) => {
      const p = adaptProfile(read(c.id, "profile.json"));
      expect(p.sections.length).toBeGreaterThan(0);
      const ids = new Set(p.evidence.map((e) => e.id));
      p.sections.flatMap((s) => s.items).forEach((i) => i.evidenceIds.forEach((id) => expect(ids.has(id)).toBe(true)));
    });
  });

  it("similar.json: 점수 0–100, 순위순, 모든 후보가 companies 에 있다", () => {
    const s = adaptSimilar(read(targetId, "similar.json"));
    expect(s.targetId).toBe(targetId);
    const known = new Set(companies.map((c) => c.id));
    s.items.forEach((it, i) => {
      expect(it.rank).toBe(i + 1);
      expect(it.scores.fused).toBeGreaterThanOrEqual(0);
      expect(it.scores.fused).toBeLessThanOrEqual(100);
      expect(known.has(it.company.id)).toBe(true);
    });
  });

  it("metrics.json: 대상기업 1행 + 후보, 지표 key 가 values 에 모두 있다", () => {
    const m = adaptMetrics(read(targetId, "metrics.json"));
    expect(m.rows.filter((r) => r.isTarget)).toHaveLength(1);
    m.rows.forEach((r) => m.metrics.forEach((d) => expect(d.key in r.values).toBe(true)));
  });

  it("network.json: 어댑터가 읽을 수 있다(비어 있어도 됨)", () => {
    const n = adaptNetwork(read(targetId, "network.json"));
    expect(n.companyId).toBe(targetId);
  });
});
