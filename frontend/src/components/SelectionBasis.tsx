import { useState } from "react";
import { AREAS } from "../lib/scoring";
import EvidenceDialog from "./EvidenceDialog";
import type { AreaKey, AreaScores, Explanation } from "../types/domain";

interface Props { data: Explanation; targetName: string; peerName: string; areaScores?: AreaScores | null; mock: boolean }

/** 영역별 선정 근거(시안 03/06): 영역 점수 · 설명 · 대상/비교기업 수치 · 근거 확인 */
export default function SelectionBasis({ data, targetName, peerName, areaScores, mock }: Props) {
  const [open, setOpen] = useState<AreaKey | null>(null);
  const byArea = new Map(data.areas.map((a) => [a.area, a]));
  return (
    <div className="basis-panel">
      <div className="row-between">
        <h3>{peerName} · 선정 근거</h3>
        {(!mock || data.coverage != null) && <span className="badge">{[!mock ? "AI 생성 설명" : "", data.coverage != null ? `자료 충족률 ${Math.round(data.coverage)}%` : ""].filter(Boolean).join(" · ")}</span>}
      </div>
      <div className="grid2 tight">
        {AREAS.map((a) => {
          const ex = byArea.get(a.key);
          if (!ex) return null;
          const sc = areaScores?.[a.key] ?? ex.score;
          return (
            <section className="ev-card" key={a.key}>
              <div className="row-between"><b>{a.label}</b><span className="mono blue">{sc === null ? "—" : `${Math.round(sc)} / 100`}</span></div>
              <p>{ex.text || "설명이 없습니다."}</p>
              {ex.compare && (
                <div className="ev-compare"><span>{ex.compare.targetLabel} {ex.compare.targetValue}</span><span>{ex.compare.peerLabel} {ex.compare.peerValue}</span></div>
              )}
              {ex.evidenceIds.length > 0
                ? <button className="link ulink" aria-haspopup="dialog" onClick={() => setOpen(a.key)}>대상·비교기업 근거 확인</button>
                : <span className="small muted">연결된 근거가 없습니다.</span>}
            </section>
          );
        })}
      </div>
      <p className="note">
        {mock ? "점수와 설명은 데모용 사전 설정값이며 실제 근거 문서·모델 결과·LLM 생성 설명은 미연결 상태입니다." : `AI가 생성한 설명이므로 근거와 함께 확인하세요.${data.model ? ` (모델 ${data.model})` : ""}`}
      </p>
      {open && byArea.get(open) && (
        <EvidenceDialog title={AREAS.find((x) => x.key === open)!.label} area={byArea.get(open)!} data={data} targetName={targetName} peerName={peerName} mock={mock} onClose={() => setOpen(null)} />
      )}
    </div>
  );
}
