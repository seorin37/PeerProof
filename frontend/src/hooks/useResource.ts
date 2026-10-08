import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, toApiError } from "../api/errors";

export type ResourceStatus = "idle" | "loading" | "success" | "empty" | "error";

export interface Resource<T> {
  status: ResourceStatus;
  data: T | null;
  error: ApiError | null;
  reload: () => void;
}

interface Snap<T> { key: string | null; status: ResourceStatus; data: T | null; error: ApiError | null }

const cache = new Map<string, unknown>();
/** 테스트·개발용: 캐시 초기화 */
export const clearResourceCache = () => cache.clear();

/**
 * key 가 null 이면 요청하지 않습니다(idle). key 가 바뀌면 이전 요청은 취소되고 새로 요청합니다.
 * 성공 결과는 key 별로 메모리에 캐시되어, 단계를 오가도 다시 요청하지 않습니다(reload 는 캐시 무시).
 */
export function useResource<T>(
  key: string | null,
  fetcher: (signal: AbortSignal) => Promise<T>,
  isEmpty: (data: T) => boolean = () => false,
): Resource<T> {
  const fetchRef = useRef(fetcher);
  const emptyRef = useRef(isEmpty);
  fetchRef.current = fetcher;
  emptyRef.current = isEmpty;

  const [snap, setSnap] = useState<Snap<T>>({ key: null, status: "idle", data: null, error: null });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (key === null) {
      setSnap({ key: null, status: "idle", data: null, error: null });
      return;
    }
    if (nonce === 0 && cache.has(key)) {
      const data = cache.get(key) as T;
      setSnap({ key, status: emptyRef.current(data) ? "empty" : "success", data, error: null });
      return;
    }
    const ctrl = new AbortController();
    setSnap({ key, status: "loading", data: null, error: null });
    fetchRef.current(ctrl.signal)
      .then((data) => {
        if (ctrl.signal.aborted) return;
        cache.set(key, data);
        setSnap({ key, status: emptyRef.current(data) ? "empty" : "success", data, error: null });
      })
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setSnap({ key, status: "error", data: null, error: toApiError(e) });
      });
    return () => ctrl.abort();
  }, [key, nonce]);

  const reload = useCallback(() => {
    if (key !== null) cache.delete(key);
    setNonce((n) => n + 1);
  }, [key]);

  // key 가 막 바뀐 첫 렌더에서 이전 key 의 결과가 잠깐 보이지 않도록 loading 으로 취급
  if (key !== null && snap.key !== key) return { status: "loading", data: null, error: null, reload };
  return { status: snap.status, data: snap.data, error: snap.error, reload };
}
