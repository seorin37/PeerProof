import { useEffect, useState } from "react";

interface Props {
  title: string;
  /** 0–100. 백엔드가 진행률을 주지 않으면 생략 → 진행 막대는 무한 애니메이션 */
  progress?: number;
  note?: string;
  onCancel?: () => void;
}

/** 전체 화면 로딩(시안 05). 진행률이 있을 때만 % 를 표시합니다. */
export default function Loading({ title, progress, note, onCancel }: Props) {
  const [sec, setSec] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setSec((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="loading" role="status" aria-live="polite">
      <div className="loading-inner">
        <small className="mono">PEER PROOF / PROCESSING</small>
        <h2>{title}</h2>
        {progress !== undefined ? (
          <div className="pct mono">{Math.round(progress)} <span>%</span></div>
        ) : (
          <div className="pct mono elapsed">{sec}<span>초 경과</span></div>
        )}
        <div className={`lbar ${progress === undefined ? "indeterminate" : ""}`}>
          <i style={progress !== undefined ? { width: `${progress}%` } : undefined} />
        </div>
        <small className="mono">{note ?? "서버에서 분석 중입니다"}</small>
        {onCancel && <button className="btn slim ghost" onClick={onCancel}>취소</button>}
      </div>
    </div>
  );
}
