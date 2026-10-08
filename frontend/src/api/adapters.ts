/**
 * ⚠ PROVISIONAL — 백엔드 JSON 필드는 아직 확정되지 않았습니다.
 * 지금은 FastAPI/Pydantic 에서 흔한 snake_case 를 가정한 "임시" 매핑이며,
 * 실제 스키마가 확정되면 이 파일만 고치면 됩니다(화면·도메인 타입은 그대로).
 *
 * 원칙: 필수 필드가 없으면 ApiError('shape')로 실패시키고, 선택 필드는 없으면 생략합니다.
 */
import type {
  BusinessProfile, CompanyNetwork, CompanySummary, EvidenceRef, ExplainStatement, Explanation,
  PerPeer, PerStats, SimilarCompany, SimilarResult, Valuation,
} from "../types/domain";
import { ApiError } from "./errors";

type Rec = Record<string, unknown>;

/** 백엔드 점수가 0–1 이면 100, 이미 0–100 이면 1 로 바꾸세요. */
export const SCORE_SCALE = 100;

const fail = (where: string, why: string): never => {
  throw new ApiError("shape", `${where}: ${why}`);
};
const rec = (v: unknown, where: string): Rec =>
  v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Rec) : fail(where, "객체가 아닙니다");
const list = (v: unknown, where: string): unknown[] =>
  v == null ? [] : Array.isArray(v) ? v : fail(where, "배열이 아닙니다");
const str = (v: unknown, where: string): string =>
  typeof v === "string" && v !== "" ? v : typeof v === "number" ? String(v) : fail(where, "문자열이 없습니다");
const optStr = (v: unknown): string | undefined => (typeof v === "string" && v !== "" ? v : undefined);
const num = (v: unknown, where: string): number =>
  typeof v === "number" && Number.isFinite(v) ? v : fail(where, "숫자가 아닙니다");
const optNum = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const ids = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);
const score = (v: unknown): number | null => {
  const n = optNum(v);
  return n === null ? null : n * SCORE_SCALE;
};

function adaptEvidence(v: unknown, where: string): EvidenceRef {
  const r = rec(v, where);
  return {
    id: str(r.id, `${where}.id`),
    source: optStr(r.source) ?? "출처 미상",
    locator: optStr(r.locator),
    url: optStr(r.url),
    publishedAt: optStr(r.published_at),
    quote: optStr(r.quote),
  };
}

function adaptCompany(v: unknown, where: string): CompanySummary {
  const r = rec(v, where);
  return {
    id: str(r.company_id ?? r.id, `${where}.company_id`),
    name: str(r.name, `${where}.name`),
    sector: optStr(r.sector),
    industry: optStr(r.industry),
    market: optStr(r.market),
  };
}

export function adaptCompanies(json: unknown): CompanySummary[] {
  const items = Array.isArray(json) ? json : list(rec(json, "companies").items, "companies.items");
  return items.map((c, i) => adaptCompany(c, `companies[${i}]`));
}

export function adaptProfile(json: unknown): BusinessProfile {
  const r = rec(json, "profile");
  return {
    companyId: str(r.company_id, "profile.company_id"),
    companyName: str(r.company_name, "profile.company_name"),
    industry: optStr(r.industry),
    period: optStr(r.period),
    basis: optStr(r.basis),
    version: optStr(r.version),
    generatedAt: optStr(r.generated_at),
    summary: optStr(r.summary),
    sections: list(r.sections, "profile.sections").map((s, i) => {
      const sr = rec(s, `profile.sections[${i}]`);
      return {
        key: str(sr.key, `profile.sections[${i}].key`),
        label: str(sr.label, `profile.sections[${i}].label`),
        items: list(sr.items, `profile.sections[${i}].items`).map((it, j) => {
          const ir = rec(it, `profile.sections[${i}].items[${j}]`);
          const value = ir.value;
          return {
            key: str(ir.key, "item.key"),
            label: str(ir.label, "item.label"),
            value: value === null || value === undefined || value === "" ? "미확인" : String(value),
            evidenceIds: ids(ir.evidence_ids),
            status: optStr(ir.status),
          };
        }),
      };
    }),
    evidence: list(r.evidence, "profile.evidence").map((e, i) => adaptEvidence(e, `profile.evidence[${i}]`)),
  };
}

export function adaptSimilar(json: unknown): SimilarResult {
  const r = rec(json, "similar");
  const f = r.fusion == null ? undefined : rec(r.fusion, "similar.fusion");
  const items: SimilarCompany[] = list(r.items, "similar.items").map((v, i) => {
    const ir = rec(v, `similar.items[${i}]`);
    return {
      rank: num(ir.rank, `similar.items[${i}].rank`),
      company: adaptCompany(ir, `similar.items[${i}]`),
      scores: {
        fused: (score(ir.fused_score) ?? fail(`similar.items[${i}]`, "fused_score 가 없습니다")),
        embedding: score(ir.embedding_score),
        network: score(ir.network_score),
      },
    };
  });
  items.sort((a, b) => a.rank - b.rank);
  return {
    targetId: str(r.target_id, "similar.target_id"),
    fusion: f
      ? { embeddingWeight: num(f.embedding_weight, "fusion.embedding_weight"), networkWeight: num(f.network_weight, "fusion.network_weight"), method: optStr(f.method) }
      : undefined,
    items,
  };
}

export function adaptNetwork(json: unknown): CompanyNetwork {
  const r = rec(json, "network");
  const nodes = list(r.nodes, "network.nodes").map((n, i) => {
    const nr = rec(n, `network.nodes[${i}]`);
    return { id: str(nr.id, "node.id"), label: str(nr.label, "node.label"), centrality: optNum(nr.centrality) ?? 0, group: optStr(nr.group) };
  });
  const known = new Set(nodes.map((n) => n.id));
  const edges = list(r.edges, "network.edges")
    .map((e, i) => {
      const er = rec(e, `network.edges[${i}]`);
      return { source: str(er.source, "edge.source"), target: str(er.target, "edge.target"), weight: optNum(er.weight) ?? 0 };
    })
    .filter((e) => known.has(e.source) && known.has(e.target)); // 존재하지 않는 노드를 가리키는 간선은 버림
  return { companyId: str(r.company_id, "network.company_id"), nodes, edges };
}

function adaptStatements(v: unknown, where: string): ExplainStatement[] {
  return list(v, where).map((s, i) => {
    const sr = rec(s, `${where}[${i}]`);
    return { text: str(sr.text, `${where}[${i}].text`), evidenceIds: ids(sr.evidence_ids) };
  });
}

export function adaptExplanation(json: unknown): Explanation {
  const r = rec(json, "explanation");
  return {
    targetId: str(r.target_id, "explanation.target_id"),
    peerId: str(r.peer_id, "explanation.peer_id"),
    summary: optStr(r.summary) ?? "",
    similarities: adaptStatements(r.similarities, "explanation.similarities"),
    differences: adaptStatements(r.differences, "explanation.differences"),
    evidence: list(r.evidence, "explanation.evidence").map((e, i) => adaptEvidence(e, `explanation.evidence[${i}]`)),
    generatedAt: optStr(r.generated_at),
    model: optStr(r.model),
  };
}

export function adaptValuation(json: unknown): Valuation {
  const r = rec(json, "valuation");
  const peers: PerPeer[] = list(r.peers, "valuation.peers").map((p, i) => {
    const pr = rec(p, `valuation.peers[${i}]`);
    return {
      companyId: str(pr.company_id, "peer.company_id"),
      name: str(pr.name, "peer.name"),
      per: optNum(pr.per),
      included: pr.included === true,
      note: optStr(pr.note),
    };
  });
  let stats: PerStats | null = null;
  if (r.stats != null) {
    const s = rec(r.stats, "valuation.stats");
    stats = { min: optNum(s.min), q1: optNum(s.q1), median: optNum(s.median), mean: optNum(s.mean), q3: optNum(s.q3), max: optNum(s.max) };
  }
  let priceBand: Valuation["priceBand"];
  if (r.price_band != null) {
    const b = rec(r.price_band, "valuation.price_band");
    priceBand = { low: num(b.low, "price_band.low"), high: num(b.high, "price_band.high") };
  }
  return {
    targetId: str(r.target_id, "valuation.target_id"),
    currency: optStr(r.currency),
    basis: optStr(r.basis),
    peers,
    stats,
    priceBand,
    notes: list(r.notes, "valuation.notes").filter((n): n is string => typeof n === "string"),
  };
}
