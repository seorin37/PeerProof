import { useState } from "react";
import { api } from "../api";
import AsyncBoundary from "../components/AsyncBoundary";
import ExplanationPanel from "../components/ExplanationPanel";
import { PageHead } from "../components/Layout";
import Loading from "../components/Loading";
import NetworkPanel from "../components/NetworkPanel";
import ScoreBar from "../components/ScoreBar";
import { ErrorBox } from "../components/AsyncBoundary";
import { describeError } from "../api/errors";
import { useResource } from "../hooks/useResource";
import type { CompanySummary, SimilarCompany, SimilarResult } from "../types/domain";

interface Props { company: CompanySummary; onBack: () => void; onNext: () => void }

function PeerDetail({ target, peer }: { target: CompanySummary; peer: SimilarCompany }) {
  const tn = useResource(`network:${target.id}`, (s) => api.getNetwork(target.id, s), (n) => n.nodes.length === 0);
  const pn = useResource(`network:${peer.company.id}`, (s) => api.getNetwork(peer.company.id, s), (n) => n.nodes.length === 0);
  const ex = useResource(`explain:${target.id}:${peer.company.id}`, (s) => api.getExplanation(target.id, peer.company.id, s));
  return (
    <div className="peer-detail">
      <h3>언어네트워크 비교</h3>
      <AsyncBoundary res={pn} rows={5} label="네트워크" emptyText="이 기업의 네트워크 데이터가 없습니다.">
        {(net) => <NetworkPanel target={tn.data} peer={net} targetName={target.name} peerName={peer.company.name} />}
      </AsyncBoundary>
      <h3>유사점·차이점 (RAG + LLM)</h3>
      <AsyncBoundary res={ex} rows={5} label="비교 설명" emptyText="비교 설명이 아직 없습니다.">
        {(d) => <ExplanationPanel data={d} />}
      </AsyncBoundary>
    </div>
  );
}

function Ranking({ company, r, onNext, onBack }: { company: CompanySummary; r: SimilarResult; onNext: () => void; onBack: () => void }) {
  const [open, setOpen] = useState<string | null>(r.items[0]?.company.id ?? null);
  const avg = r.items.reduce((a, x) => a + x.scores.fused, 0) / r.items.length;
  return (
    <>
      {r.fusion && (
        <div className="info-bar">
          Late Fusion: 임베딩(BGE-M3) {Math.round(r.fusion.embeddingWeight * 100)}% + 언어네트워크 {Math.round(r.fusion.networkWeight * 100)}%
          {r.fusion.method ? ` · ${r.fusion.method}` : ""}
        </div>
      )}
      <section className="card">
        <div className="card-head pad"><h2>유사기업 Top {r.items.length}</h2><small>행을 눌러 네트워크와 비교 설명을 확인합니다.</small></div>
        <div className="table sim-table">
          <div className="tr th"><span>순위</span><span>기업</span><span>종합 유사도</span><span>임베딩</span><span>네트워크</span></div>
          {r.items.map((it) => {
            const on = open === it.company.id;
            return (
              <div key={it.company.id}>
                <button className={`tr sim-row ${on ? "sel" : ""}`} aria-expanded={on} onClick={() => setOpen(on ? null : it.company.id)}>
                  <span className="mono">{it.rank}</span>
                  <span className="peer-name"><b>{it.company.name}</b><small>{it.company.industry ?? ""}</small></span>
                  <span className="total mono">{it.scores.fused.toFixed(1)}</span>
                  <ScoreBar value={it.scores.embedding} label="임베딩 유사도" />
                  <ScoreBar value={it.scores.network} label="네트워크 유사도" tone="main" />
                </button>
                {on && <div className="evidence"><PeerDetail target={company} peer={it} /></div>}
              </div>
            );
          })}
        </div>
      </section>
      <div className="summary">
        <div><small>비교기업</small><div className="big mono">{r.items.length}개</div></div>
        <div className="vr" />
        <div><small>평균 종합 유사도</small><div className="big mono">{avg.toFixed(1)}</div></div>
        <button className="btn primary" onClick={onNext}>PER 비교 보기</button>
      </div>
      <div className="actions"><span /><div className="btns"><button className="btn" onClick={onBack}>이전</button></div></div>
    </>
  );
}

export default function Step3({ company, onBack, onNext }: Props) {
  const res = useResource(`similar:${company.id}`, (s) => api.getSimilar(company.id, s), (r: SimilarResult) => r.items.length === 0);
  return (
    <>
      {res.status === "loading" && <Loading title="유사기업을 찾는 중입니다" onCancel={onBack} note="임베딩과 언어네트워크 유사도를 결합합니다." />}
      <PageHead step={2} eyebrow="PEER SELECTION" title="유사기업 Top 5" sub={`${company.name}과(와) 사업 구조가 가까운 기업입니다.`} />
      {res.status === "error" && res.error && <ErrorBox message={describeError(res.error)} onRetry={res.reload} label="유사기업" />}
      {res.status === "empty" && <div className="empty">유사기업을 찾지 못했습니다.</div>}
      {res.status === "success" && res.data && <Ranking company={company} r={res.data} onNext={onNext} onBack={onBack} />}
      {(res.status === "error" || res.status === "empty") && (
        <div className="actions"><span /><div className="btns"><button className="btn" onClick={onBack}>이전</button></div></div>
      )}
    </>
  );
}
