import { PerRow, RankRow, Valuation, rankedOnly } from "../lib/engine";
import { eok, parseNum, won } from "../lib/format";
import type { Settings } from "../lib/types";
import { Footer, Page } from "../components/Layout";

interface Props {
  settings: Settings;
  setSettings: (s: Settings) => void;
  rows: RankRow[];
  perRows: PerRow[];
  valuation: Valuation;
  onPrev: () => void;
  onReset: () => void;
}

const Num = ({ value, onChange, unit, neg = false, readOnly = false }: { value: number; onChange?: (n: number) => void; unit: string; neg?: boolean; readOnly?: boolean }) => (
  <span className={`input ${readOnly ? "ro" : ""}`}>
    <input inputMode="numeric" readOnly={readOnly} value={Number.isFinite(value) ? value.toLocaleString("ko-KR") : ""} onChange={(e) => onChange?.(parseNum(e.target.value, neg))} />
    <em>{unit}</em>
  </span>
);

export default function Step4({ settings: s, setSettings, rows, perRows, valuation: v, onPrev, onReset }: Props) {
  const set = <K extends keyof Settings>(k: K, val: Settings[K]) => setSettings({ ...s, [k]: val });
  const pctIn = (k: "discMin" | "discMax", val: string) => set(k, Math.min(100, parseNum(val)) / 100);
  const ok = v.error == null;
  const invalidDisc = s.discMin > s.discMax;
  const used = rankedOnly(rows).filter((r) => perRows.find((p) => p.id === r.peer.id)?.included);
  const perOf = (id: string) => perRows.find((p) => p.id === id)?.per ?? null;
  const dMin = s.discMin * 100;
  const dMax = s.discMax * 100;
  const pers = used.map((r) => (perOf(r.peer.id) as number).toFixed(1));

  return (
    <Page step={4} mode={s.mode} eyebrow="VALUATION RESULT" title="근거에서, 가치로." sub="선택한 비교기업의 PER 분포를 바탕으로 예상 공모가 밴드를 계산합니다.">
      <section className="hero">
        <div>
          <small className="mono">ESTIMATED OFFERING PRICE / {s.mode === "예시" ? "DEMO" : "CONFIRMED"}</small>
          <div className="hero-label">예상 공모가 밴드</div>
          <div className="hero-band mono">{ok ? `${won(v.low)} — ${won(v.high)} 원` : "산출 보류"}</div>
          <div className="hero-note">{ok ? `${s.targetName} · 할인율 ${dMin.toFixed(0)}–${dMax.toFixed(0)}% 적용 · ${won(s.roundUnit)}원 단위 내림 · 확정 공모가 아님` : v.error}</div>
        </div>
        <div className="hero-side">
          <small>할인 전 주당 평가액 (Q1 – Q3)</small>
          <div className="mono">{ok ? `${won(v.lowPre)} – ${won(v.highPre)}` : "—"} 원</div>
          <small>평가용 EPS</small>
          <div className="mono">{won(v.eps)} 원</div>
        </div>
      </section>

      <section className="card kpis">
        <div><small>PER 하단 Q1</small><div className="mono">{v.q1 != null ? v.q1.toFixed(1) : "—"} 배</div></div>
        <div><small>PER 중앙값 · 참고</small><div className="mono">{v.median != null ? v.median.toFixed(1) : "—"} 배</div></div>
        <div><small>PER 상단 Q3</small><div className="mono">{v.q3 != null ? v.q3.toFixed(1) : "—"} 배</div></div>
        <div><small>선택 비교기업 · 이익 기준</small><div className="mono">{String(v.count).padStart(2, "0")} 개 <span className="kr">{s.period} {s.fsBasis === "CFS" ? "연결" : "별도"}</span></div></div>
      </section>

      <section className="card kpis offer">
        <div><small>공모금액 (하단 – 상단)</small><div className="mono">{ok ? `${eok(v.offerLow)} – ${eok(v.offerHigh)}` : "—"} 억 원</div></div>
        <div><small>회사 신주 유입액 (비용 공제 전)</small><div className="mono">{ok ? `${eok(v.inflowLow)} – ${eok(v.inflowHigh)}` : "—"} 억 원</div></div>
        <div><small>총 공모 주식수 (신주 + 구주)</small><div className="mono">{v.offerShares != null ? won(v.offerShares) : "—"} 주</div></div>
        <div><small>IPO 후 평가 주식수</small><div className="mono">{won(v.sharesPost)} 주</div></div>
      </section>

      <div className="two">
        <section className="card pad">
          <div className="card-head"><h2>공모 할인율 설정</h2><span className="muted small">직접 입력</span></div>
          <p className="small muted">할인율이 높을수록 예상 공모가는 낮아집니다. 하단에는 최대, 상단에는 최소 할인율을 적용합니다.</p>
          <div className="grid2 tight">
            <label><span className="lbl">최소 할인율 (상단)</span><span className="input"><input inputMode="decimal" value={+dMin.toFixed(2)} onChange={(e) => pctIn("discMin", e.target.value)} /><em>%</em></span></label>
            <label><span className="lbl">최대 할인율 (하단)</span><span className="input"><input inputMode="decimal" value={+dMax.toFixed(2)} onChange={(e) => pctIn("discMax", e.target.value)} /><em>%</em></span></label>
          </div>
          {invalidDisc && <div className="warn">최소 할인율이 최대 할인율보다 클 수 없습니다.</div>}
          <div className="track">
            <div className="bar"><i style={{ left: `${dMin}%`, width: `${Math.max(0, dMax - dMin)}%` }} /></div>
            <div className="ticks mono"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div>
          </div>
          <div className="track price">
            <div className="bar thin">
              {!invalidDisc && <i style={{ left: `${100 - dMax}%`, width: `${Math.max(0, dMax - dMin)}%` }} />}
              <b className="end" />
            </div>
            <div className="row-between small muted"><span>0원</span><span>할인 전 주당 평가액 상단 {won(v.highPre)}원</span></div>
          </div>
          <p className="small muted formula">하단 = Q1 PER × EPS × (1 − 최대 할인율)<br />상단 = Q3 PER × EPS × (1 − 최소 할인율)<br />절사 단위 {won(s.roundUnit)}원 · 통계적 신뢰구간이 아닌 예시 범위입니다.</p>
        </section>

        <section className="card pad">
          <div className="card-head"><h2>평가 가정</h2><span className="muted small">{s.mode === "예시" ? "가상 입력값" : "확정 입력값"}</span></div>
          <div className="shares">
            <label><span className="lbl">귀속 당기순이익</span><Num value={s.netIncome} readOnly unit="원" /></label>
            <span className="plus">+</span>
            <label><span className="lbl">정상화 조정액</span><Num value={s.normAdj} neg onChange={(n) => set("normAdj", n)} unit="원" /></label>
          </div>
          <div className="shares">
            <label><span className="lbl">IPO 전 기준 주식수</span><Num value={s.sharesPre} readOnly unit="주" /></label>
            <span className="plus">+</span>
            <label><span className="lbl">신주 발행 수</span><Num value={s.sharesNew} onChange={(n) => set("sharesNew", n)} unit="주" /></label>
          </div>
          <div className="shares tri">
            <label><span className="lbl">추가 희석 주식수</span><Num value={s.sharesDilution} onChange={(n) => set("sharesDilution", n)} unit="주" /></label>
            <label><span className="lbl">구주 매출 수</span><Num value={s.sharesSecondary} onChange={(n) => set("sharesSecondary", n)} unit="주" /></label>
          </div>
          <div className="total-shares"><span>= IPO 후 평가 주식수</span><b className="mono">{won(v.sharesPost)} 주</b></div>
          <p className="small muted">구주 매출은 공모금액에는 포함되지만 IPO 후 주식수와 회사 유입액에는 더하지 않습니다. 신주 자금 유입에 따른 추가 이익은 가정하지 않습니다.</p>
          <p className="small muted">정상화 조정 근거: {s.normNote || "—"} · 대상기업 원천: {s.targetSource || "—"}</p>
          <dl className="calc mono">
            <div><dt>PER 분포</dt><dd>[{pers.join(", ")}] → Q1 {v.q1?.toFixed(1) ?? "—"} · Q3 {v.q3?.toFixed(1) ?? "—"}</dd></div>
            <div><dt>평가용 EPS</dt><dd>{eok(v.earnings)}억 ÷ {won(v.sharesPost)}주 = {won(v.eps)}원</dd></div>
            <div><dt>평가가 (할인 전)</dt><dd>{won(v.lowPre)} – {won(v.highPre)}원</dd></div>
          </dl>
        </section>
      </div>

      <div className="info-bar">유사도 가중치는 비교기업 선정에만 적용되며, 선택된 비교기업의 PER은 동일 가중으로 사분위수를 계산합니다.</div>

      <section className="card">
        <div className="card-head pad">
          <div><h2>평가에 사용한 비교기업</h2><div className="small muted">동일 이익 기간({s.period}) · 동일 시총 기준일({s.asOf}) 기준 {s.mode === "예시" ? "가상 " : ""}PER</div></div>
          <button className="link" onClick={onPrev}>선택 변경</button>
        </div>
        <div className="table used">
          <div className="tr th"><span>기업명</span><span>산업 설명</span><span>종합유사도</span><span>적용 PER</span></div>
          {used.map((r) => (
            <div className="tr" key={r.peer.id}>
              <span>{r.peer.name}{s.mode === "예시" ? " · 예시" : ""}</span><span>{r.peer.industry}</span>
              <span className="mono">{(r.total as number).toFixed(1)}</span><span className="mono blue">{(perOf(r.peer.id) as number).toFixed(1)}×</span>
            </div>
          ))}
          {used.length === 0 && <div className="tr"><span className="muted">선택된 비교기업이 없습니다.</span></div>}
        </div>
      </section>
      <p className="small muted pad-x0">공모·신주 유입액은 비용 공제 전 금액입니다. 수수료·세금·실권·초과배정은 별도 검토 대상입니다.</p>

      <Footer hint="평가 결과는 선택 기업과 입력 가정에 따라 달라집니다.">
        <button className="btn" onClick={onPrev}>비교기업 다시 검토</button>
        <button className="btn primary" onClick={onReset}>처음부터 평가</button>
      </Footer>
    </Page>
  );
}
