export type ApiMode = "mock" | "live";
export type Scenario = "ok" | "error" | "empty" | "slow";

/** VITE_API_MODE=live 일 때만 실제 백엔드를 호출합니다. 기본값은 mock. */
export const API_MODE: ApiMode = import.meta.env.VITE_API_MODE === "live" ? "live" : "mock";
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");
export const REQUEST_TIMEOUT_MS = 20_000;

/**
 * Mock 모드 상태 시험용: 주소 뒤에 ?mock=error | empty | slow 를 붙입니다.
 * 특정 자원만: ?mock=error:similar,network  (자원 이름은 api/routes.ts 의 RouteKey)
 */
export function scenarioFor(resource: string): Scenario {
  if (typeof window === "undefined") return "ok";
  const v = new URLSearchParams(window.location.search).get("mock");
  if (!v) return "ok";
  const [name, targets] = v.split(":");
  if (name !== "error" && name !== "empty" && name !== "slow") return "ok";
  if (targets && !targets.split(",").includes(resource)) return "ok";
  return name;
}
