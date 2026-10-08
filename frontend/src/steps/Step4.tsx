import { api } from "../api";
import AsyncBoundary from "../components/AsyncBoundary";
import { PageHead } from "../components/Layout";
import { deriveStats } from "../lib/network";
import { useResource } from "../hooks/useResource";
import type { CompanySummary, Valuation } from "../types/domain";

interface Props { company: CompanySummary; onBack: () => void; onReset: () => void }

const fmt = (n: number | null | undefined, d = 1) => (n === null || n === undefined ? "—" : n.toFixed(d));

function Result({ v }: { v: Valuation }) {
  const incl = v.peers.filter((p) => p.included && p.per !== null);
  const derived = deriveStats(incl.map((p) => p.per as number));
  const min = v.stats?.min ?? derived?.min ?? null;
  const med = v.stats?.median ?? derived?.median ?? null;
  const max = v.stats?.max ?? derived?.max ?? null;
  const top = Math.max(...v.peers.map((p) => p.per ?? 0), max ?? 0, 1);
  const cur = v.currency ?? "원";
  return (
    <>
      <section className="hero">
        <div>
          <small>PER BASED REFERENCE</small>
          {v.priceBand ? (
            <>
              <div className="hero-label">참고 가격 범위</div>
              <div className="hero-band mono">{v.priceBand.low.toLocaleString()} ~ {v.priceBand.high.toLocaleString()}<span className="kr">{cur}</span></div>
            </>
          ) : (
            <>
              <div className="hero-label">비교기업 PER 범위</div>
              <div className="hero-band mono">{fmt(min)} ~ {fmt(max)}<span className="kr">배</span></div>
            </>
          )}
          <div className="hero-note">{v.basis ?? "비교기업 PER 기준 참고 범위이며 투자 권유가 아닙니다."}</div>
        </div>
        <div className="hero-side">
          <small>MEDIAN PER</small><div className="mono">{fmt(med)}배</div>
          <small>INCLUDED PEERS</small><div className="mono">{incl.length} / {v.peers.length}</div>
        </div>
      </section>
      <section className="card pad kpis">
        {[["최소", min], ["중앙값", med], ["최대", max]].map(([l, x]) => (
          <div key={l as string}><small>{l as string}</small><div className="mono">{fmt(x as number | null)}<span className="kr">배</span></div></div>
        ))}
        <div><small>평균</small><div className="mono">{fmt(v.stats?.mean)}<span className="kr">배</span></div></div>
      </section>
      <section className="card pad">
        <div className="card-head"><h2>비교기업 PER</h2></div>
        <div className="perchart" role="img" aria-label="비교기업 PER 막대 차트">
          {med !== null && <span className="medline" style={{ bottom: `${(med / top) * 100}%` }}><em className="mono">중앙값 {fmt(med)}</em></span>}
          {v.peers.map((p) => (
            <div key={p.companyId} className={`perbar ${p.included && p.per !== null ? "" : "off"}`}>
              <i style={{ height: `${p.per === null ? 0 : (p.per / top) * 100}%` }} />
              <b className="mono">{fmt(p.per)}</b><span>{p.name}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="card">
        <div className="table used">
          <div className="tr th"><span>기업</span><span>PER</span><span>산정 포함</span><span>비고</span></div>
          {v.peers.map((p) => (
            <div className="tr" key={p.companyId}>
              <span>{p.name}</span><span className="mono">{fmt(p.per)}</span>
              <span>{p.included ? "포함" : "제외"}</span><span className="small muted">{p.note ?? ""}</span>
            </div>
          ))}
        </div>
      </section>
      {v.notes.map((n, i) => <div className="info-bar" key={i}>{n}</div>)}
    </>
  );
}

export default function Step4({ company, onBack, onReset }: Props) {
  const res = useResource(`valuation:${company.id}`, (s) => api.getValuation(company.id, s), (v: Valuation) => v.peers.length === 0);
  return (
    <>
      <PageHead step={3} eyebrow="VALUATION RESULT" title="PER 비교 결과" sub={`${company.name} 비교기업의 PER 분포입니다.`} />
      <AsyncBoundary res={res} rows={6} label="가치평가 결과" emptyText="PER 비교에 사용할 수 있는 데이터가 없습니다.">
        {(v) => <Result v={v} />}
      </AsyncBoundary>
      <div className="actions">
        <span />
        <div className="btns"><button className="btn" onClick={onBack}>이전</button><button className="btn primary" onClick={onReset}>새 분석 시작</button></div>
      </div>
    </>
  );
}
