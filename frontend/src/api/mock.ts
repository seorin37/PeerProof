/** 백엔드 없이 화면을 개발하기 위한 Mock 서버. api/index.ts 가 mode=mock 일 때만 사용합니다. */
import companiesJson from "../mocks/companies.json";
import explanationJson from "../mocks/explanation.json";
import networkJson from "../mocks/network.json";
import profileJson from "../mocks/profile.json";
import similarJson from "../mocks/similar.json";
import valuationJson from "../mocks/valuation.json";
import { scenarioFor } from "./config";
import { ApiError } from "./errors";
import type { RouteKey, RouteParams } from "./routes";

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

function hash(s: string): number {
  let h = 0;
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h;
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new ApiError("aborted", "요청이 취소되었습니다."));
    const t = setTimeout(() => { signal?.removeEventListener("abort", onAbort); resolve(); }, ms);
    const onAbort = () => { clearTimeout(t); reject(new ApiError("aborted", "요청이 취소되었습니다.")); };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

const nameOf = (id: string): string =>
  companiesJson.items.find((c) => c.company_id === id)?.name ??
  similarJson.items.find((c) => c.company_id === id)?.name ??
  id;

/** 비교기업마다 조금씩 다른 네트워크가 나오도록 노드 2개를 결정적으로 제외 */
function peerNetwork(peerId: string) {
  const base = clone(networkJson.peer);
  const n = base.nodes.length;
  const drop = new Set([base.nodes[hash(peerId) % n].id, base.nodes[(hash(peerId) + 3) % n].id]);
  return {
    company_id: peerId,
    nodes: base.nodes.filter((x) => !drop.has(x.id)),
    edges: base.edges.filter((e) => !drop.has(e.source) && !drop.has(e.target)),
  };
}

const BUILD: Record<RouteKey, (p: RouteParams) => unknown> = {
  companies: (p) => {
    const q = (p.query ?? "").trim().toLowerCase();
    return { items: companiesJson.items.filter((c) => !q || `${c.name} ${c.industry} ${c.sector}`.toLowerCase().includes(q)) };
  },
  profile: (p) => {
    const id = p.companyId ?? "TGT";
    return { ...clone(profileJson), company_id: id, company_name: nameOf(id) };
  },
  similar: (p) => ({ ...clone(similarJson), target_id: p.companyId ?? "TGT" }),
  network: (p) => {
    const id = p.companyId ?? "TGT";
    const isPeer = similarJson.items.some((i) => i.company_id === id);
    return isPeer ? peerNetwork(id) : { ...clone(networkJson.target), company_id: id };
  },
  explanation: (p) => {
    const text = JSON.stringify(explanationJson)
      .replaceAll("{target}", nameOf(p.companyId ?? "TGT"))
      .replaceAll("{peer}", nameOf(p.peerId ?? ""));
    return { ...(JSON.parse(text) as object), target_id: p.companyId, peer_id: p.peerId };
  },
  valuation: (p) => ({ ...clone(valuationJson), target_id: p.companyId ?? "TGT" }),
};

const EMPTY: Record<RouteKey, (p: RouteParams) => unknown> = {
  companies: () => ({ items: [] }),
  profile: (p) => ({ company_id: p.companyId, company_name: nameOf(p.companyId ?? ""), sections: [], evidence: [] }),
  similar: (p) => ({ target_id: p.companyId, items: [] }),
  network: (p) => ({ company_id: p.companyId, nodes: [], edges: [] }),
  explanation: (p) => ({ target_id: p.companyId, peer_id: p.peerId, summary: "", similarities: [], differences: [], evidence: [] }),
  valuation: (p) => ({ target_id: p.companyId, peers: [], notes: [] }),
};

export async function mockFetch(key: RouteKey, params: RouteParams, signal?: AbortSignal): Promise<unknown> {
  const scenario = scenarioFor(key);
  await delay(scenario === "slow" ? 3500 : 350 + (hash(JSON.stringify(params)) % 350), signal);
  if (scenario === "error") throw new ApiError("mock", "Mock 오류 시나리오입니다 (주소의 ?mock=error).");
  return scenario === "empty" ? EMPTY[key](params) : BUILD[key](params);
}
