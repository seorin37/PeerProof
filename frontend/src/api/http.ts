import { API_BASE_URL, REQUEST_TIMEOUT_MS } from "./config";
import { ApiError } from "./errors";

export interface RequestOptions {
  signal?: AbortSignal;
  query?: Record<string, string | undefined>;
  timeoutMs?: number;
}

/** 실제 백엔드 호출용 GET 요청. 타임아웃·취소·HTTP 오류·JSON 오류를 ApiError 로 통일합니다. */
export async function getJson(path: string, opts: RequestOptions = {}): Promise<unknown> {
  const qs = new URLSearchParams();
  Object.entries(opts.query ?? {}).forEach(([k, v]) => v !== undefined && v !== "" && qs.set(k, v));
  const url = `${API_BASE_URL}${path}${qs.toString() ? `?${qs}` : ""}`;

  const ctrl = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; ctrl.abort(); }, opts.timeoutMs ?? REQUEST_TIMEOUT_MS);
  const onAbort = () => ctrl.abort();
  if (opts.signal?.aborted) ctrl.abort();
  opts.signal?.addEventListener("abort", onAbort);

  try {
    const res = await fetch(url, { headers: { Accept: "application/json" }, signal: ctrl.signal });
    if (!res.ok) {
      let detail = "";
      try {
        const body = (await res.json()) as { detail?: unknown };
        if (typeof body?.detail === "string") detail = body.detail; // FastAPI 기본 오류 형식
      } catch { /* 본문이 JSON 이 아니면 무시 */ }
      throw new ApiError("http", detail, res.status);
    }
    try {
      return await res.json();
    } catch {
      throw new ApiError("shape", "JSON 으로 해석할 수 없는 응답입니다.");
    }
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof DOMException && e.name === "AbortError") {
      throw timedOut ? new ApiError("timeout", "요청 시간이 초과되었습니다.") : new ApiError("aborted", "요청이 취소되었습니다.");
    }
    throw new ApiError("network", e instanceof Error ? e.message : "네트워크 오류");
  } finally {
    clearTimeout(timer);
    opts.signal?.removeEventListener("abort", onAbort);
  }
}
