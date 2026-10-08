import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { buildPerRows, rankPeers, rankedOnly, valuate } from "./engine";
import { parseWorkbook } from "./workbook";

const data = parseWorkbook(new Uint8Array(readFileSync("public/sample.xlsx")));
const s = data.settings;
const target = data.companies.find((c) => c.id === s.targetId)!;
const peers = data.companies.filter((c) => c.id !== s.targetId);

describe("엑셀(02_유사도계산 / 03_PER밴드) 값과 일치", () => {
  const rows = rankPeers(s, target, peers, s.weights);
  const byId = Object.fromEntries(rows.map((r) => [r.peer.id, r]));

  it("필터 깔때기: 후보 7 → BM 6 → 점수 산출 5", () => {
    expect(rows.filter((r) => r.pass1).length).toBe(7);
    expect(rows.filter((r) => r.pass2).length).toBe(6);
    expect(rows.filter((r) => r.total != null).length).toBe(5);
    expect(byId.P06.status).toBe("산업 제외");
    expect(byId.P05.status).toBe("BM 제외");
    expect(byId.P08.status).toBe("근거·가중치·필드 확인");
  });

  it("가중 점수와 순위", () => {
    expect(byId.P01.total).toBeCloseTo(89.7, 6);
    expect(byId.P02.total).toBeCloseTo(86.7, 6);
    expect(byId.P03.total).toBeCloseTo(85.875, 6);
    expect(byId.P07.total).toBeCloseTo(78.11666666666667, 6);
    expect(byId.P04.total).toBeCloseTo(65.25, 6);
    expect(rankedOnly(rows).map((r) => r.peer.id)).toEqual(["P01", "P02", "P03", "P07", "P04"]);
  });

  it("PER 밴드: Q1 20.5 / 중앙값 21 / Q3 23.5, 공모가 14,300–19,900", () => {
    const per = buildPerRows(s, rows, data.perInputs, data.perInputs.filter((p) => p.selected).map((p) => p.id));
    const v = valuate(s, per);
    expect(v.error).toBeNull();
    expect([v.q1, v.median, v.q3]).toEqual([20.5, 21, 23.5]);
    expect(v.eps).toBe(1000);
    expect([v.low, v.high]).toEqual([14300, 19900]);
    expect(v.offerShares).toBe(2500000);
    expect([v.offerLow, v.offerHigh]).toEqual([35750000000, 49750000000]);
    expect([v.inflowLow, v.inflowHigh]).toEqual([28600000000, 39800000000]);
  });

  it("적자 기업(P07)은 PER 산출 불가로 선택 불가", () => {
    const per = buildPerRows(s, rows, data.perInputs, ["P07"]);
    const p07 = per.find((r) => r.id === "P07")!;
    expect(p07.blocker).toBe("적자 · PER 산출 불가");
    expect(p07.included).toBe(false);
  });

  it("비교기업이 최소 개수 미만이면 밴드 산출 보류", () => {
    const per = buildPerRows(s, rows, data.perInputs, ["P01", "P02"]);
    expect(valuate(s, per).error).toBe("기업 수 부족 / 설정 확인");
  });
});
