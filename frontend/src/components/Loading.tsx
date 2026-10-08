import { useEffect, useState } from "react";

interface Stage { from: number; no: string; title: string; note: string }

/** 엑셀 02·03단계(산업 1차 필터 → 대상 프로필 작성)를 보여주는 진행 화면. 현재는 시뮬레이션이며 API 연결 시 실제 진행률로 교체. */
export default function Loading({ candidates, onDone }: { candidates: number; onDone: () => void }) {
  const [pct, setPct] = useState(0);
  const stages: Stage[] = [
    { from: 0, no: "02", title: "산업 1차 필터", note: `산업 코사인 + 임계값 + N · 후보 ${candidates}개 검토` },
    { from: 45, no: "03", title: "대상기업 비즈니스 프로필 분석", note: "RAG 검색 + LLM 구조화 · 4영역 프로필" },
  ];
  useEffect(() => {
    const start = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / 2400);
      setPct(Math.round(p * 100));
      if (p < 1) raf = requestAnimationFrame(tick);
      else onDone();
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const stage = [...stages].reverse().find((s) => pct >= s.from) as Stage;
  return (
    <div className="loading" role="status" aria-live="polite">
      <div className="loading-inner">
        <small className="mono">PEER PROOF / PROCESSING / STAGE {stage.no}</small>
        <h2>{stage.title}</h2>
        <div className="pct mono">{pct} <span>%</span></div>
        <div className="lbar"><i style={{ width: `${pct}%` }} /></div>
        <small className="mono">{stage.note} · DEMO SIMULATION</small>
      </div>
    </div>
  );
}
