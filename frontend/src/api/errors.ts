export type ApiErrorKind = "network" | "timeout" | "http" | "shape" | "aborted" | "mock";

export class ApiError extends Error {
  constructor(public kind: ApiErrorKind, message: string, public status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

export function toApiError(e: unknown): ApiError {
  if (e instanceof ApiError) return e;
  if (e instanceof DOMException && e.name === "AbortError") return new ApiError("aborted", "요청이 취소되었습니다.");
  return new ApiError("network", e instanceof Error ? e.message : "알 수 없는 오류가 발생했습니다.");
}

/** 화면에 보여줄 한국어 안내문 */
export function describeError(e: ApiError): string {
  switch (e.kind) {
    case "timeout": return "서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.";
    case "network": return "서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인해 주세요.";
    case "http": return `서버에서 오류가 반환되었습니다${e.status ? ` (HTTP ${e.status})` : ""}. ${e.message}`.trim();
    case "shape": return `서버 응답 형식이 예상과 다릅니다. ${e.message}`;
    case "mock": return e.message;
    default: return e.message;
  }
}
