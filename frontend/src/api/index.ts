/**
 * 화면이 사용하는 유일한 API 진입점.
 * mock/live 전환, 경로 조립, 응답 변환(어댑터)을 여기서 한 번에 처리합니다.
 */
import type {
  BusinessProfile, CompanyNetwork, CompanySummary, Explanation, SimilarResult, Valuation,
} from "../types/domain";
import {
  adaptCompanies, adaptExplanation, adaptNetwork, adaptProfile, adaptSimilar, adaptValuation,
} from "./adapters";
import { API_MODE } from "./config";
import { getJson } from "./http";
import { mockFetch } from "./mock";
import { ROUTES, RouteKey, RouteParams } from "./routes";

function fetchRaw(key: RouteKey, params: RouteParams, signal?: AbortSignal): Promise<unknown> {
  if (API_MODE === "mock") return mockFetch(key, params, signal);
  const { path, query } = ROUTES[key](params);
  return getJson(path, { signal, query });
}

export const api = {
  searchCompanies: async (query: string, signal?: AbortSignal): Promise<CompanySummary[]> =>
    adaptCompanies(await fetchRaw("companies", { query }, signal)),
  getProfile: async (companyId: string, signal?: AbortSignal): Promise<BusinessProfile> =>
    adaptProfile(await fetchRaw("profile", { companyId }, signal)),
  getSimilar: async (companyId: string, signal?: AbortSignal): Promise<SimilarResult> =>
    adaptSimilar(await fetchRaw("similar", { companyId }, signal)),
  getNetwork: async (companyId: string, signal?: AbortSignal): Promise<CompanyNetwork> =>
    adaptNetwork(await fetchRaw("network", { companyId }, signal)),
  getExplanation: async (companyId: string, peerId: string, signal?: AbortSignal): Promise<Explanation> =>
    adaptExplanation(await fetchRaw("explanation", { companyId, peerId }, signal)),
  getValuation: async (companyId: string, signal?: AbortSignal): Promise<Valuation> =>
    adaptValuation(await fetchRaw("valuation", { companyId }, signal)),
};

export { API_MODE };
