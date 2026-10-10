import { useMemo, useState } from "react";
import { api } from "../api";
import AsyncBoundary from "../components/AsyncBoundary";
import { PageHead } from "../components/Layout";
import { useResource } from "../hooks/useResource";
import { applyWeights, computeBand, defaultSelection, type Levels } from "../lib/scoring";
import type { CompanySummary, SimilarResult, Valuation } from "../types/domain";

interface Props {
  company: CompanySummary; levels: Levels; selected: string[] | null; onBack: () => void; onReset: () => void;
}

const won = (n: number) => `${Math.round(n).toLocaleString()}`;
const f2 = (n: number) => n.toFixed(2);
const parse = (s: string): number | null => { const n = Number(s.replace(/,/g, "")); return s.trim() !== "" && Number.isFinite(n) ? n : null; };

function Result({ v, sim, levels, selected, onBack }: { v: Valuation; sim: SimilarResult | null; levels: Levels; selected: string[] | null; onBack: () => void }) {
  const [dmin, setDmin] = useState("15");
  const [dmax, setDmax] = useState("25");
  const [newSh, setNewSh] = useState("0");
  const [niIn, setNiIn] = useState("");
  const [shIn, setShIn] = useState("");

  const ranked = useMemo(() => (sim ? applyWeights(sim, levels).items : []), [sim, levels]);
  const ids = selected ?? defaultSelection(v);
  const used = v.peers.filter((p) => ids.includes(p.companyId) && p.per !== null);
  const pers = used.map((p) => p.per as number);
  const netIncome = v.netIncome ?? parse(niIn);
  const baseShares = v.shares ?? parse(shIn);
  const lo = parse(dmin), hi = parse(dmax), ns = parse(newSh);
  const bad = lo === null || hi === null || ns === null || lo < 0 || hi > 100 || lo > hi || ns < 0;
  const band = bad ? null : computeBand({ pers, netIncomeEok: netIncome, baseShares, newShares: ns!, discMin: lo!, discMax: hi! });
  const simOf = (id: string) => ranked.find((i) => i.company.id === id)?.scores.fused;
  const cur = v.currency === "KRW" || !v.currency ? "원" : v.currency;

  return (
    <>
      <section className="hero">
        <div>
          <small>ESTIMATED OFFERING PRICE</small>
          <div className="hero-label">예상 공모가 밴드</div>
          <div className="hero-band mono">{band ? `${won(band.low)} – ${won(band.high)}` : "—"}<span className="kr">{cur}</span></div>
          <div className="hero-note">{band ? `할인율 ${lo}–${hi}% 적용 · 확정 공모가 아님` : used.length === 0 ? "선택된 비교기업이 없습니다." : "순이익·주식수·할인율 입력을 확인해 주세요."}</div>
        </div>
        <div className="hero-side">
          <small>할인 전 주당 평가액</small><div className="mono">{band ? `${won(band.perShare)} ${cur}` : "—"}</div>
          <small>지분가치 추정액</small><div className="mono">{band ? `${band.equityEok.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} 억 원` : "—"}</div>
        </div>
      </section>

      <section className="card pad kpis">
        <div><small>적용 평균 PER</small><div className="mono">{band ? f2(band.avgPer) : "—"}<span className="kr">배</span></div></div>
        <div><small>중앙값 PER · 참고</small><div className="mono">{band ? band.medianPer.toFixed(1) : "—"}<span className="kr">배</span></div></div>
        <div><small>선택 비교기업</small><div className="mono">{String(used.length).padStart(2, "0")}<span className="kr">개</span></div></div>
        <div><small>이익 기준</small><div className="mono">{v.basis?.split("·")[0].trim() ?? "—"}</div></div>
      </section>

      <div className="two">
        <section className="card pad">
          <div className="card-head"><h2>공모 할인율 설정</h2><small>직접 입력</small></div>
          <p className="muted-d small">할인율이 높을수록 예상 공모가는 낮아집니다.</p>
          <div className="grid2 tight" style={{ marginTop: 14 }}>
            <label><span className="lbl">최소 할인율</span><span className="input"><input inputMode="decimal" value={dmin} onChange={(e) => setDmin(e.target.value)} aria-label="최소 할인율" /><em>%</em></span></label>
            <label><span className="lbl">최대 할인율</span><span className="input"><input inputMode="decimal" value={dmax} onChange={(e) => setDmax(e.target.value)} aria-label="최대 할인율" /><em>%</em></span></label>
          </div>
          {bad && <div className="warn" role="alert">할인율은 0~100% 이며 최소 ≤ 최대여야 하고, 신주 수는 0 이상이어야 합니다.</div>}
          <div className="track">
            <div className="bar"><i style={{ left: `${lo ?? 0}%`, width: `${Math.max(0, (hi ?? 0) - (lo ?? 0))}%` }} /></div>
            <div className="ticks"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div>
          </div>
          <div className="track">
            <div className="bar thin"><i style={{ left: `${100 - (hi ?? 0)}%`, width: `${Math.max(0, (hi ?? 0) - (lo ?? 0))}%` }} /><span className="end" /></div>
            <div className="ticks"><span>0{cur}</span><span>할인 전 주당 평가액 {band ? won(band.perShare) : "—"}{cur}</span></div>
          </div>
          <div className="formula small muted-d mono">하단 = 주당 평가액 × (1 − 최대 할인율)<br />상단 = 주당 평가액 × (1 − 최소 할인율)</div>
        </section>

        <section className="card pad">
          <div className="card-head"><h2>평가 가정</h2></div>
          <div className="shares">
            <label><span className="lbl">기존 발행주식수</span>
              {v.shares != null
                ? <span className="input ro" aria-readonly="true"><span className="roval mono">{v.shares.toLocaleString()}</span><em>만 주</em></span>
                : <span className="input"><input inputMode="decimal" value={shIn} onChange={(e) => setShIn(e.target.value)} aria-label="기존 발행주식수" /><em>만 주</em></span>}
            </label>
            <span className="plus">+</span>
            <label><span className="lbl">IPO 신규 발행주식수</span>
              <span className="input"><input inputMode="decimal" value={newSh} onChange={(e) => setNewSh(e.target.value)} aria-label="IPO 신규 발행주식수" /><em>만 주</em></span></label>
          </div>
          <div className="total-shares"><span>= 적용 주식수</span><b className="mono">{baseShares !== null && ns !== null ? `${(baseShares + ns).toLocaleString()} 만 주` : "—"}</b></div>
          {v.netIncome == null && (
            <label><span className="lbl">대상기업 순이익</span><span className="input"><input inputMode="decimal" value={niIn} onChange={(e) => setNiIn(e.target.value)} aria-label="순이익" /><em>억 원</em></span></label>
          )}
          <p className="note">기존 주식수·순이익은 {v.shares != null && v.netIncome != null ? "제공값(프로필)이 자동 반영되며" : "제공되지 않아 직접 입력이 필요하며"}, 전환증권·공모자금 유입은 자동 반영되지 않습니다.</p>
          <dl className="calc mono">
            <div><dt>PER 산술평균</dt><dd>{pers.length ? `(${pers.map((p) => p.toFixed(1)).join(" + ")}) ÷ ${pers.length}` : "—"}</dd></div>
            <div><dt>지분가치 추정액</dt><dd>{band && netIncome !== null ? `${f2(band.avgPer)} × ${netIncome.toLocaleString()}억` : "—"}</dd></div>
            <div><dt>주당 평가액</dt><dd>{band ? `${band.equityEok.toLocaleString(undefined, { maximumFractionDigits: 1 })}억 ÷ ${band.totalShares.toLocaleString()}만 주` : "—"}</dd></div>
          </dl>
        </section>
      </div>

      <div className="info-bar">유사도 가중치는 비교기업 선정에만 적용되며, 평가 PER은 선택 기업의 산술평균입니다. {v.notes.join(" ")}</div>

      <section className="card">
        <div className="card-head pad"><div><h2>평가에 사용한 비교기업</h2><small>동일 이익 기간 · 동일 주가 기준일을 가정한 PER</small></div><button className="link" onClick={onBack}>선택 변경</button></div>
        <div className="table used">
          <div className="tr th"><span>기업명</span><span>산업분류</span><span>종합유사도</span><span>적용 PER</span></div>
          {used.map((p) => {
            const it = ranked.find((i) => i.company.id === p.companyId);
            return (
              <div className="tr" key={p.companyId}>
                <span>{p.name}</span><span className="muted small">{it?.company.industry ?? "—"}</span>
                <span className="mono">{simOf(p.companyId)?.toFixed(1) ?? "—"}</span><span className="mono blue perval">{p.per!.toFixed(1)}×</span>
              </div>
            );
          })}
        </div>
        {used.length === 0 && <div className="empty">선택된 비교기업이 없습니다. 이전 단계에서 비교기업을 선택해 주세요.</div>}
      </section>
    </>
  );
}

export default function Step4({ company, levels, selected, onBack, onReset }: Props) {
  const res = useResource(`valuation:${company.id}`, (s) => api.getValuation(company.id, s), (v: Valuation) => v.peers.length === 0);
  const sim = useResource(`similar:${company.id}`, (s) => api.getSimilar(company.id, s));
  return (
    <>
      <PageHead step={3} eyebrow="VALUATION RESULT" title="근거에서, 가치로." sub="선택한 비교기업의 PER을 바탕으로 예상 공모가 밴드를 계산합니다." />
      <AsyncBoundary res={res} rows={6} label="가치평가 결과" emptyText="PER 비교에 사용할 수 있는 데이터가 없습니다.">
        {(v) => <Result v={v} sim={sim.data} levels={levels} selected={selected} onBack={onBack} />}
      </AsyncBoundary>
      <div className="actions">
        <span className="hint">평가 결과는 선택 기업과 입력 가정에 따라 달라집니다.</span>
        <div className="btns"><button className="btn" onClick={onBack}>비교기업 다시 검토</button><button className="btn primary" onClick={onReset}>처음부터 평가</button></div>
      </div>
    </>
  );
}
