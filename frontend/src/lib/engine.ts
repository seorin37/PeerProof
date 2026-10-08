/**
 * 엑셀 02_유사도계산 · 03_PER밴드 시트의 수식을 그대로 옮긴 계산 엔진.
 * 순수 함수만 포함합니다(화면/상태와 무관).
 */
import { AREA_KEYS } from "./areas";
import type { AreaKey, Company, PerInput, Settings, Weights } from "./types";

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

export function weightsValid(w: Weights): boolean {
  const vals = AREA_KEYS.map((k) => w[k]);
  return vals.every(isNum) && Math.min(...vals) >= 0 && Math.abs(vals.reduce((s, v) => s + v, 0) - 1) < 1e-9;
}

export interface RankRow {
  peer: Company;
  indRank: number | null;
  pass1: boolean;
  bmRank: number | null;
  pass2: boolean;
  scores: Record<AreaKey, number | null>;
  total: number | null;
  rank: number | null;
  /** 엑셀 02 시트 Q열 상태 */
  status: "산업 제외" | "BM 제외" | "순위 산출" | "근거·가중치·필드 확인";
}

/** 내림차순 순위. 동점은 원천 행 순서. mask 가 false 인 행은 제외. */
function rankDesc(values: (number | null)[], mask: boolean[]): (number | null)[] {
  return values.map((v, i) => {
    if (!mask[i] || !isNum(v)) return null;
    let r = 1;
    values.forEach((o, j) => {
      if (!mask[j] || !isNum(o)) return;
      if (o > v || (o === v && j < i)) r++;
    });
    return r;
  });
}

export function rankPeers(s: Settings, target: Company, peers: Company[], weights: Weights): RankRow[] {
  const idCount = new Map<string, number>();
  peers.forEach((p) => idCount.set(p.id, (idCount.get(p.id) ?? 0) + 1));

  // 1차: 산업 코사인 (모든 행 대상으로 순위, 임계값·상한 적용)
  const indRanks = rankDesc(peers.map((p) => p.indCos), peers.map(() => true));
  const pass1 = peers.map((p, i) => {
    const c = p.indCos;
    return (
      isNum(c) && c >= -1 && c <= 1 && isNum(s.indThreshold) && isNum(s.indTopN) &&
      c >= s.indThreshold && (indRanks[i] as number) <= s.indTopN &&
      p.id !== s.targetId && idCount.get(p.id) === 1
    );
  });

  // 2차: BM 코사인 (1차 통과 기업 내 순위)
  const bmRanks = rankDesc(peers.map((p) => p.bmCos), pass1);
  const pass2 = peers.map((p, i) => {
    const c = p.bmCos;
    return (
      pass1[i] && isNum(c) && c >= -1 && c <= 1 && isNum(s.bmThreshold) && isNum(s.bmTopN) &&
      c >= s.bmThreshold && (bmRanks[i] as number) <= s.bmTopN
    );
  });

  const wOk = weightsValid(weights);
  const targetOk =
    target.id === s.targetId && isNum(target.evidence) && isNum(s.minEvidence) && target.evidence >= s.minEvidence;

  const rows = peers.map((p, i): RankRow => {
    const scores: Record<AreaKey, number | null> = { bm: null, growth: null, risk: null, fin: null };
    if (pass2[i]) {
      scores.bm = 100 * clamp01(p.bmCos as number);
      if (isNum(p.growth) && isNum(target.growth) && s.growthTol > 0)
        scores.growth = 100 * Math.max(0, 1 - Math.abs(p.growth - target.growth) / s.growthTol);
      if (isNum(p.riskCos) && p.riskCos >= -1 && p.riskCos <= 1) scores.risk = 100 * clamp01(p.riskCos);
      if (isNum(p.opMargin) && isNum(p.debtRatio) && isNum(target.opMargin) && isNum(target.debtRatio) && s.finTol > 0)
        scores.fin =
          50 *
          (Math.max(0, 1 - Math.abs(p.opMargin - target.opMargin) / s.finTol) +
            Math.max(0, 1 - Math.abs(p.debtRatio - target.debtRatio) / s.finTol));
    }
    const allScores = AREA_KEYS.every((k) => isNum(scores[k]));
    const evOk = isNum(p.evidence) && p.evidence >= s.minEvidence && p.evidence <= 1;
    const modeOk = s.mode === "예시" || (s.mode === "확정" && p.status === "확정" && target.status === "확정");
    const total =
      pass2[i] && allScores && evOk && wOk && targetOk && modeOk
        ? AREA_KEYS.reduce((sum, k) => sum + (scores[k] as number) * weights[k], 0)
        : null;
    return {
      peer: p,
      indRank: indRanks[i],
      pass1: pass1[i],
      bmRank: bmRanks[i],
      pass2: pass2[i],
      scores,
      total,
      rank: null,
      status: !pass1[i] ? "산업 제외" : !pass2[i] ? "BM 제외" : total != null ? "순위 산출" : "근거·가중치·필드 확인",
    };
  });

  const totals = rows.map((r) => r.total);
  const ranks = rankDesc(totals, totals.map((t) => t != null));
  rows.forEach((r, i) => (r.rank = ranks[i]));
  return rows;
}

/** 순위 산출된 기업만 총점 내림차순(동점 시 원천 순서) */
export const rankedOnly = (rows: RankRow[]) =>
  rows.filter((r) => r.total != null).sort((a, b) => (a.rank as number) - (b.rank as number));

export function explainExclusion(r: RankRow, s: Settings): string {
  const p = r.peer;
  if (!r.pass1)
    return isNum(p.indCos)
      ? `산업 코사인 ${p.indCos.toFixed(2)} (임계값 ${s.indThreshold.toFixed(2)} 미만 또는 상위 ${s.indTopN}개 밖)`
      : "산업 코사인 입력 확인";
  if (!r.pass2)
    return isNum(p.bmCos)
      ? `BM 코사인 ${p.bmCos.toFixed(2)} (임계값 ${s.bmThreshold.toFixed(2)} 미만 또는 상위 ${s.bmTopN}개 밖)`
      : "BM 코사인 입력 확인";
  if (isNum(p.evidence) && p.evidence < s.minEvidence)
    return `근거 충족률 ${(p.evidence * 100).toFixed(0)}% (최소 ${(s.minEvidence * 100).toFixed(0)}% 미만) · 점수 보류`;
  return "근거·가중치·필드·검증 상태 확인";
}

export interface PerRow {
  id: string;
  marketCap: number | null;
  earnings: number | null;
  per: number | null;
  selected: boolean;
  /** 선택 불가 사유 (null이면 선택 가능) */
  blocker: string | null;
  included: boolean;
}

export function buildPerRows(s: Settings, ranked: RankRow[], inputs: PerInput[], selectedIds: string[]): PerRow[] {
  const inMap = new Map(inputs.map((i) => [i.id, i]));
  return ranked.map((r): PerRow => {
    const i = inMap.get(r.peer.id);
    const mc = i?.marketCap ?? null;
    const ea = i?.earnings ?? null;
    const per = isNum(mc) && isNum(ea) && mc > 0 && ea > 0 ? mc / ea : null;
    const consistent =
      !!i && s.period !== "" && s.currency !== "" && (s.fsBasis === "CFS" || s.fsBasis === "OFS") &&
      i.period === s.period && i.currency === s.currency && i.basis === s.fsBasis && i.asOf === s.asOf &&
      (s.mode === "예시" || (s.mode === "확정" && i.status === "확정"));
    const blocker =
      r.total == null ? "순위·근거 확인"
      : !consistent ? "기간·기준·상태 확인"
      : per == null ? (isNum(ea) && ea <= 0 ? "적자 · PER 산출 불가" : "시총·이익 확인")
      : per > s.perCap ? `PER 상한 초과 (${s.perCap}배)`
      : null;
    const selected = selectedIds.includes(r.peer.id);
    return { id: r.peer.id, marketCap: mc, earnings: ea, per, selected, blocker, included: selected && blocker == null };
  });
}

/** 엑셀 QUARTILE (포괄적 방식, 선형 보간) */
export function quartile(values: number[], q: number): number {
  const a = [...values].sort((x, y) => x - y);
  const pos = (a.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return a[lo] + (a[hi] - a[lo]) * (pos - lo);
}

export interface Valuation {
  count: number;
  error: string | null;
  q1: number | null;
  median: number | null;
  q3: number | null;
  earnings: number | null;
  sharesPost: number | null;
  eps: number | null;
  lowPre: number | null;
  highPre: number | null;
  low: number | null;
  high: number | null;
  offerShares: number | null;
  offerLow: number | null;
  offerHigh: number | null;
  inflowLow: number | null;
  inflowHigh: number | null;
}

export function valuate(s: Settings, perRows: PerRow[]): Valuation {
  const pers = perRows.filter((r) => r.included).map((r) => r.per as number);
  const v: Valuation = {
    count: pers.length, error: null, q1: null, median: null, q3: null, earnings: null, sharesPost: null, eps: null,
    lowPre: null, highPre: null, low: null, high: null, offerShares: null, offerLow: null, offerHigh: null,
    inflowLow: null, inflowHigh: null,
  };
  const countOk = isNum(s.minPeers) && s.minPeers >= 1 && pers.length >= s.minPeers;
  if (countOk) {
    v.q1 = quartile(pers, 0.25);
    v.median = quartile(pers, 0.5);
    v.q3 = quartile(pers, 0.75);
  }
  v.earnings = isNum(s.netIncome) && isNum(s.normAdj) ? s.netIncome + s.normAdj : null;
  const sharesNums = [s.sharesPre, s.sharesNew, s.sharesDilution];
  const sharesReady = sharesNums.every(isNum) && isNum(s.sharesSecondary);
  v.sharesPost = sharesNums.every(isNum) && s.sharesPre > 0 && Math.min(s.sharesNew, s.sharesDilution) >= 0
    ? s.sharesPre + s.sharesNew + s.sharesDilution : null;
  v.eps = isNum(v.earnings) && v.earnings > 0 && isNum(v.sharesPost) && v.sharesPost > 0 ? v.earnings / v.sharesPost : null;

  const int = (n: number) => Number.isInteger(n);
  const inputOk =
    sharesReady && isNum(v.eps) &&
    [s.discMax, s.discMin, s.roundUnit].every(isNum) &&
    s.discMax >= s.discMin && s.discMin >= 0 && s.discMax < 1 && s.roundUnit > 0 &&
    s.sharesSecondary >= 0 && s.sharesSecondary <= s.sharesPre &&
    [s.sharesPre, s.sharesNew, s.sharesDilution, s.sharesSecondary].every(int) &&
    (s.mode === "예시" || (s.mode === "확정" && s.earningsStatus === "확정" && s.sharesStatus === "확정"));

  if (!countOk) v.error = "기업 수 부족 / 설정 확인";
  else if (!sharesReady) v.error = "주식수 입력 확인";
  else if (!inputOk) v.error = "이익·주식수·할인·상태 확인";
  if (v.error) return v;

  const eps = v.eps as number;
  v.lowPre = eps * (v.q1 as number);
  v.highPre = eps * (v.q3 as number);
  const cut = (price: number, disc: number) => Math.floor((price * (1 - disc)) / s.roundUnit) * s.roundUnit;
  v.low = cut(v.lowPre, s.discMax);
  v.high = cut(v.highPre, s.discMin);
  v.offerShares = s.sharesNew + s.sharesSecondary;
  v.offerLow = v.low * v.offerShares;
  v.offerHigh = v.high * v.offerShares;
  v.inflowLow = v.low * s.sharesNew;
  v.inflowHigh = v.high * s.sharesNew;
  return v;
}
