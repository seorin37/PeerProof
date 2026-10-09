/**
 * ⚠ PROVISIONAL — 백엔드 API 경로는 아직 확정되지 않았습니다.
 * 경로가 정해지면 이 파일만 수정하세요. 화면 코드는 RouteKey 만 사용합니다.
 */
export type RouteKey = "companies" | "profile" | "similar" | "network" | "explanation" | "metrics";

export interface RouteParams {
  query?: string;
  companyId?: string;
  peerId?: string;
}

interface Built {
  path: string;
  query?: Record<string, string | undefined>;
}

const enc = encodeURIComponent;

export const ROUTES: Record<RouteKey, (p: RouteParams) => Built> = {
  companies: (p) => ({ path: "/companies", query: { query: p.query } }),
  profile: (p) => ({ path: `/companies/${enc(p.companyId ?? "")}/profile` }),
  similar: (p) => ({ path: `/companies/${enc(p.companyId ?? "")}/similar` }),
  network: (p) => ({ path: `/companies/${enc(p.companyId ?? "")}/network` }),
  explanation: (p) => ({ path: `/companies/${enc(p.companyId ?? "")}/explanations/${enc(p.peerId ?? "")}` }),
  metrics: (p) => ({ path: `/companies/${enc(p.companyId ?? "")}/metrics` }),
};
