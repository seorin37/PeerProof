import { ReactNode } from "react";
import { describeError } from "../api/errors";
import type { Resource } from "../hooks/useResource";

interface Props<T> {
  res: Resource<T>;
  emptyText: string;
  children: (data: T) => ReactNode;
  /** 로딩 중 스켈레톤 줄 수 */
  rows?: number;
  label?: string;
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skel-block" aria-busy="true" aria-label="불러오는 중">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton" style={{ width: `${92 - ((i * 17) % 40)}%` }} />
      ))}
    </div>
  );
}

export function ErrorBox({ message, onRetry, label }: { message: string; onRetry?: () => void; label?: string }) {
  return (
    <div className="state-error" role="alert">
      <span><b>{label ? `${label}을(를) ` : ""}불러오지 못했습니다.</b><br />{message}</span>
      {onRetry && <button className="btn slim" onClick={onRetry}>다시 시도</button>}
    </div>
  );
}

/** 로딩 / 오류 / 데이터 없음 / 성공 상태를 한 곳에서 처리합니다. */
export default function AsyncBoundary<T>({ res, emptyText, children, rows, label }: Props<T>) {
  if (res.status === "idle") return null;
  if (res.status === "loading") return <Skeleton rows={rows} />;
  if (res.status === "error" && res.error) return <ErrorBox message={describeError(res.error)} onRetry={res.reload} label={label} />;
  if (res.status === "empty" || res.data === null) return <div className="empty">{emptyText}</div>;
  return <>{children(res.data)}</>;
}
