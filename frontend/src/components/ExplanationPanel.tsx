import { useState } from "react";
import type { EvidenceRef, ExplainStatement, Explanation } from "../types/domain";

function Statements({ title, items, evidence, active, onPick }: {
  title: string; items: ExplainStatement[]; evidence: EvidenceRef[]; active: string | null; onPick: (id: string) => void;
}) {
  const index = new Map(evidence.map((e, i) => [e.id, i + 1]));
  return (
    <div className="stmt">
      <h4>{title}</h4>
      {items.length === 0 && <p className="small muted">해당 내용이 없습니다.</p>}
      <ul>
        {items.map((s, i) => (
          <li key={i}>
            {s.text}
            {s.evidenceIds.map((id) => (
              <button key={id} className={`evchip ${active === id ? "on" : ""}`} onClick={() => onPick(id)} aria-label={`근거 ${index.get(id) ?? id}`}>
                {index.get(id) ?? "?"}
              </button>
            ))}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** RAG + LLM 비교 설명. 문장 뒤 번호를 누르면 아래 근거 목록에서 해당 근거가 강조됩니다. */
export default function ExplanationPanel({ data }: { data: Explanation }) {
  const [active, setActive] = useState<string | null>(null);
  return (
    <div className="expl">
      {data.summary && <p className="expl-summary">{data.summary}</p>}
      <div className="grid2 tight">
        <Statements title="유사점" items={data.similarities} evidence={data.evidence} active={active} onPick={setActive} />
        <Statements title="차이점" items={data.differences} evidence={data.evidence} active={active} onPick={setActive} />
      </div>
      <div className="evlist">
        <h4>근거</h4>
        {data.evidence.length === 0 && <p className="small muted">연결된 근거가 없습니다.</p>}
        <ol>
          {data.evidence.map((e, i) => (
            <li key={e.id} className={active === e.id ? "on" : ""}>
              <span className="evno">{i + 1}</span>
              <div>
                <b>{e.source}</b>{e.locator ? ` · ${e.locator}` : ""}{e.publishedAt ? ` · ${e.publishedAt}` : ""}
                {e.quote && <blockquote>{e.quote}</blockquote>}
                {e.url && <a href={e.url} target="_blank" rel="noreferrer">원문 보기 ↗</a>}
              </div>
            </li>
          ))}
        </ol>
      </div>
      {(data.generatedAt || data.model) && (
        <p className="small muted">생성 {data.generatedAt ?? "—"}{data.model ? ` · 모델 ${data.model}` : ""} · AI가 생성한 설명이므로 근거와 함께 확인하세요.</p>
      )}
    </div>
  );
}
