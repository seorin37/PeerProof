import { useEffect, useRef } from "react";
import type { AreaExplanation, Explanation } from "../types/domain";

interface Props {
  title: string; // 영역 이름
  area: AreaExplanation;
  data: Explanation;
  targetName: string;
  peerName: string;
  mock: boolean;
  onClose: () => void;
}

const MISSING = "미연결";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="dlg-row"><small>{label}</small><div>{children}</div></div>;
}

/** 대상·비교기업 근거 페이지(시안 06 팝업). Esc / 바깥 클릭 / 닫기 버튼으로 닫습니다. */
export default function EvidenceDialog({ title, area, data, targetName, peerName, mock, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => { document.body.style.overflow = prev; window.removeEventListener("keydown", onKey); };
  }, [onClose]);

  const ev = new Map(data.evidence.map((e) => [e.id, e]));
  const c = area.compare;
  return (
    <div className="dlg-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dlg" role="dialog" aria-modal="true" aria-labelledby="dlg-title">
        <div className="dlg-head">
          <h2 id="dlg-title">대상·비교기업 근거</h2>
          <button ref={closeRef} className="btn slim" onClick={onClose}>닫기</button>
        </div>
        {mock && <div className="info-bar">데모용 설명입니다. 실제 보고서·접수일·공시 링크는 연결되어 있지 않습니다.</div>}
        <Row label="항목">{title}</Row>
        <Row label={`대상기업 값 · ${targetName}`}>{c ? `${c.targetLabel} ${c.targetValue}` : MISSING}</Row>
        <Row label="비교기업">{peerName}{c ? ` · ${c.peerLabel} ${c.peerValue}` : ""}</Row>
        <Row label="근거 / 계산 기준">{area.text || MISSING}</Row>
        {area.evidenceIds.length === 0 && <Row label="보고서명">{MISSING} · 연결된 근거가 없습니다</Row>}
        {area.evidenceIds.map((id, i) => {
          const e = ev.get(id);
          return (
            <div className="dlg-ev" key={id}>
              {area.evidenceIds.length > 1 && <b className="dlg-evno">근거 {i + 1}</b>}
              <Row label="보고서명">{e?.source ?? `${MISSING} · 근거 ${id} 상세 없음`}</Row>
              <Row label="접수일">{e?.publishedAt ?? MISSING}</Row>
              <Row label="섹션">{e?.locator ?? MISSING}</Row>
              {e?.quote && <Row label="원문 발췌">{e.quote}</Row>}
              <Row label="원문 링크">{e?.url ? <a href={e.url} target="_blank" rel="noreferrer">원문 보기 ↗</a> : `${MISSING} · 공시 원문 없음`}</Row>
            </div>
          );
        })}
        {data.period && <Row label="기준 기간 · 회계 범위 · 단위">{data.period}</Row>}
      </div>
    </div>
  );
}
