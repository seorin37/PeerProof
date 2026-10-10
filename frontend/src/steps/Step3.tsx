import { useMemo, useState } from "react";
import { api, API_MODE } from "../api";
import { describeError } from "../api/errors";
import AsyncBoundary, { ErrorBox } from "../components/AsyncBoundary";
import SelectionBasis from "../components/SelectionBasis";
import { PageHead } from "../components/Layout";
import Loading from "../components/Loading";
import NetworkPanel from "../components/NetworkPanel";
import { useResource } from "../hooks/useResource";
import { AREAS, applyWeights, canWeigh, defaultSelection, mean, toPercents, type Levels } from "../lib/scoring";
import type { CompanySummary, SimilarCompany, SimilarResult, Valuation } from "../types/domain";

interface Props {
  company: CompanySummary; levels: Levels; selected: string[] | null; onSelect: (ids: string[]) => void;
  onEditCriteria: () => void; onBack: () => void; onNext: () => void;
}

function PeerDetail({ target, peer }: { target: CompanySummary; peer: SimilarCompany }) {
  const tn = useResource(`network:${target.id}`, (s) => api.getNetwork(target.id, s), (n) => n.nodes.length === 0);
  const pn = useResource(`network:${peer.company.id}`, (s) => api.getNetwork(peer.company.id, s), (n) => n.nodes.length === 0);
  const ex = useResource(`explain:${target.id}:${peer.company.id}`, (s) => api.getExplanation(target.id, peer.company.id, s), (d) => d.areas.length === 0);
  return (
    <div className="peer-detail">
      <AsyncBoundary res={ex} rows={5} label="선정 근거" emptyText="선정 근거 설명이 아직 없습니다.">
        {(d) => <SelectionBasis data={d} targetName={target.name} peerName={peer.company.name} areaScores={peer.scores.areas} mock={API_MODE === "mock"} />}
      </AsyncBoundary>
      <h4 className="subh">언어네트워크 비교</h4>
      <AsyncBoundary res={pn} rows={5} label="네트워크" emptyText="이 기업의 네트워크 데이터가 없습니다.">
        {(net) => <NetworkPanel target={tn.data} peer={net} peerName={peer.company.name} />}
      </AsyncBoundary>
    </div>
  );
}

const x = (n: number | null | undefined) => (n === null || n === undefined ? "N/A" : `${n.toFixed(1)}×`);
const Cell = ({ v }: { v: number | null | undefined }) => <span className="score"><b>{v == null ? "—" : Math.round(v)}</b><u /></span>;

function Ranking({ p }: { p: Props & { r: SimilarResult; val: Valuation | null } }) {
  const { company, r, val, levels, onEditCriteria, onBack, onNext } = p;
  const [open, setOpen] = useState<string | null>(null);
  const [showExcl, setShowExcl] = useState(false);
  const perOf = useMemo(() => new Map((val?.peers ?? []).map((x) => [x.companyId, x])), [val]);
  const eligible = r.items.filter((i) => perOf.get(i.company.id)?.per != null).map((i) => i.company.id);
  const sel = new Set((p.selected ?? defaultSelection(val)).filter((id) => eligible.includes(id)));
  const set = (ids: Iterable<string>) => p.onSelect([...ids]);
  const toggle = (id: string) => { const n = new Set(sel); n.has(id) ? n.delete(id) : n.add(id); set(n); };
  const allOn = eligible.length > 0 && eligible.every((id) => sel.has(id));
  const pers = [...sel].map((id) => perOf.get(id)?.per).filter((v): v is number => v != null);
  const avg = mean(pers);
  const excluded = r.items.filter((i) => !eligible.includes(i.company.id));
  const weighed = canWeigh(r);
  const pc = toPercents(levels);

  return (
    <>
      <div className="card weights">
        <div className="wctl">
          {AREAS.map((a) => <span key={a.key} className="small">{a.label} <b className="mono">{Math.round(pc[a.key])}%</b></span>)}
        </div>
        <button className="link" onClick={onEditCriteria}>기준 조정</button>
      </div>
      {r.fusion && (
        <div className="info-bar">
          Late Fusion: 임베딩(BGE-M3) {Math.round(r.fusion.embeddingWeight * 100)}% + 언어네트워크 {Math.round(r.fusion.networkWeight * 100)}%
          {weighed ? " · 영역 중요도가 임베딩 점수에 반영되었습니다." : " · 백엔드가 영역별 점수를 주지 않아 중요도는 점수에 반영되지 않았습니다."}
        </div>
      )}
      <div className="list-head row-between"><h2>비교기업 후보 {String(r.items.length).padStart(2, "0")}</h2><small>유사도 높은 순 · 전체 기업</small></div>
      <div className="table peers">
        <div className="tr th">
          <span className="cb-cell"><input type="checkbox" className="cb" aria-label="전체 선택" checked={allOn} disabled={eligible.length === 0} onChange={() => set(allOn ? [] : eligible)} />기업명 / 산업분류</span>
          <span>Business</span><span>Growth</span><span>Risk</span><span>Finance</span><span>종합유사도</span><span>PER</span><span>PBR</span>
        </div>
        {r.items.map((it) => {
          const id = it.company.id; const pv = perOf.get(id); const ok = eligible.includes(id); const on = open === id;
          const a = it.scores.areas;
          return (
            <div key={id}>
              <div className={`tr peer ${sel.has(id) ? "sel" : ""} ${ok ? "" : "dis"}`}>
                <span className="cb-cell">
                  <input type="checkbox" className="cb" checked={sel.has(id)} disabled={!ok} aria-label={`${it.company.name} 선택`} onChange={() => toggle(id)} />
                  <button className="peer-name" aria-expanded={on} onClick={() => setOpen(on ? null : id)}>
                    <b>{it.company.name}<i className="link">{on ? "−" : "+"}</i></b>
                    <small>{[it.company.industry, !ok ? "PER 산출 불가 · 선택 불가" : ""].filter(Boolean).join(" · ")}</small>
                  </button>
                </span>
                <Cell v={a?.bm} /><Cell v={a?.growth} /><Cell v={a?.risk} /><Cell v={a?.fin} />
                <span className="score"><b className="total">{it.scores.fused.toFixed(1)}</b>
                  <small>임베딩 {it.scores.embedding?.toFixed(0) ?? "—"} · 네트워크 {it.scores.network?.toFixed(0) ?? "—"}</small></span>
                <span className="mono perval">{x(pv?.per)}</span><span className="mono perval">{x(pv?.pbr)}</span>
              </div>
              {on && <div className="evidence"><PeerDetail target={company} peer={it} /></div>}
            </div>
          );
        })}
      </div>
      <p className="note">기업명을 누르면 언어네트워크와 영역별 비교 설명(근거 포함)을 확인할 수 있습니다.</p>
      {excluded.length > 0 && (
        <button className="card excl" aria-expanded={showExcl} onClick={() => setShowExcl(!showExcl)}>
          기준 미충족 기업 {excluded.length}개 · 제외 사유 확인
          {showExcl && <div className="excl-body">{excluded.map((i) => <div key={i.company.id}>{i.company.name}: {perOf.get(i.company.id)?.note ?? "PER 정보가 없어 선택할 수 없습니다."}</div>)}</div>}
        </button>
      )}
      <div className="summary">
        <div><small>선택한 비교기업</small><div className="big mono">{sel.size} 개</div></div>
        <div className="vr" />
        <div><small>평균 PER</small><div className="big mono">{avg === null ? "—" : `${avg.toFixed(2)} 배`}</div></div>
        <button className="btn primary" disabled={sel.size === 0} onClick={() => { p.onSelect([...sel]); onNext(); }}>가치평가 결과 보기</button>
      </div>
      <div className="actions"><span className="hint">선택을 바꾸면 평균 PER이 즉시 갱신됩니다.</span><div className="btns"><button className="btn" onClick={onBack}>이전 단계</button></div></div>
    </>
  );
}

export default function Step3(props: Props) {
  const { company, levels, onBack } = props;
  const sim = useResource(`similar:${company.id}`, (s) => api.getSimilar(company.id, s), (r: SimilarResult) => r.items.length === 0);
  const val = useResource(`valuation:${company.id}`, (s) => api.getValuation(company.id, s));
  const weighted = useMemo(() => (sim.data ? applyWeights(sim.data, levels) : null), [sim.data, levels]);
  return (
    <>
      {sim.status === "loading" && <Loading title="비교기업을 탐색하는 중입니다" onCancel={onBack} note="임베딩과 언어네트워크 유사도를 결합합니다." />}
      <PageHead step={2} eyebrow="PEER SELECTION" title="비교기업을 검토하세요." sub="유사도와 선정 근거를 확인하고, 평가에 사용할 기업을 선택하세요." />
      {sim.status === "error" && sim.error && <ErrorBox message={describeError(sim.error)} onRetry={sim.reload} label="비교기업" />}
      {sim.status === "empty" && <div className="empty">비교기업을 찾지 못했습니다.</div>}
      {val.status === "error" && val.error && <ErrorBox message={describeError(val.error)} onRetry={val.reload} label="PER 정보" />}
      {sim.status === "success" && weighted && <Ranking p={{ ...props, r: weighted, val: val.data }} />}
      {(sim.status === "error" || sim.status === "empty") && <div className="actions"><span /><div className="btns"><button className="btn" onClick={onBack}>이전 단계</button></div></div>}
    </>
  );
}
