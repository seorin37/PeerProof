import { Fragment, useState } from "react";
import { AREAS, AREA_KEYS } from "../lib/areas";
import { PerRow, RankRow, Valuation, explainExclusion, rankedOnly } from "../lib/engine";
import { pct1, x1 } from "../lib/format";
import type { Company, Settings, Weights } from "../lib/types";
import { Footer, Page } from "../components/Layout";

interface Props {
  settings: Settings;
  target: Company;
  setSettings: (s: Settings) => void;
  pct: Weights;
  rows: RankRow[];
  perRows: PerRow[];
  valuation: Valuation;
  setSelected: (ids: string[]) => void;
  selectedIds: string[];
  onPrev: () => void;
  onNext: () => void;
  onAdjust: () => void;
}

export default function Step3({ settings: s, target, setSettings, pct, rows, perRows, valuation: v, selectedIds, setSelected, onPrev, onNext, onAdjust }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showExcl, setShowExcl] = useState(false);
  const ranked = rankedOnly(rows);
  const excluded = rows.filter((r) => r.total == null);
  const perMap = new Map(perRows.map((p) => [p.id, p]));
  const selectable = ranked.filter((r) => perMap.get(r.peer.id)?.blocker == null);
  const allOn = selectable.length > 0 && selectable.every((r) => selectedIds.includes(r.peer.id));
  const included = perRows.filter((p) => p.included).length;
  const funnel = [
    ["후보 (전체)", rows.length], ["산업 필터 통과", rows.filter((r) => r.pass1).length],
    ["BM 필터 통과", rows.filter((r) => r.pass2).length], ["점수 산출", ranked.length], ["PER 선택", included],
  ] as const;
  const toggle = (id: string) => setSelected(selectedIds.includes(id) ? selectedIds.filter((x) => x !== id) : [...selectedIds, id]);
  const num = (k: "indThreshold" | "bmThreshold" | "perCap", val: string) => {
    const n = Number(val);
    if (Number.isFinite(n) && n >= 0) setSettings({ ...s, [k]: n });
  };

  return (
    <Page step={3} mode={s.mode} eyebrow="PEER SELECTION" title="비교기업을 검토하세요." sub="유사도와 선정 근거를 확인하고, 평가에 사용할 기업을 선택하세요.">
      <section className="card weights">
        {AREAS.map((a) => <span key={a.key}>{a.label} {pct[a.key]}%</span>)}
        <button className="link" onClick={onAdjust}>기준 조정</button>
      </section>

      <section className="card pad funnel">
        <div className="card-head"><h2>필터 단계</h2><span className="muted small">산업 1차 → BM 2차 → 점수·순위 → PER 선택</span></div>
        <div className="funnel-row">
          {funnel.map(([label, n], i) => (
            <div key={label} className={i === funnel.length - 1 ? "last" : ""}><small>{label}</small><b className="mono">{n}</b></div>
          ))}
        </div>
        <div className="thresholds">
          <label>산업 코사인 임계값<input className="mini" type="number" step="0.01" min="0" max="1" value={s.indThreshold} onChange={(e) => num("indThreshold", e.target.value)} /></label>
          <label>BM 코사인 임계값<input className="mini" type="number" step="0.01" min="0" max="1" value={s.bmThreshold} onChange={(e) => num("bmThreshold", e.target.value)} /></label>
          <label>PER 상한 (배)<input className="mini" type="number" step="1" min="1" value={s.perCap} onChange={(e) => num("perCap", e.target.value)} /></label>
        </div>
      </section>

      <div className="row-between list-head">
        <h2>비교기업 후보 {String(ranked.length).padStart(2, "0")}</h2>
        <span className="small muted">종합유사도 높은 순 &nbsp;·&nbsp; 전체 {s.mode === "예시" ? "가상 " : ""}기업</span>
      </div>

      <div className="table peers">
        <div className="tr th">
          <span className="cb-cell">
            <input type="checkbox" className="cb" checked={allOn} onChange={() => setSelected(allOn ? [] : selectable.map((r) => r.peer.id))} aria-label="전체 선택" />
            기업명 / 산업분류
          </span>
          <span>Business</span><span>Growth</span><span>Risk</span><span>Finance</span><span>종합유사도</span><span>PER</span><span>근거 충족률</span>
        </div>
        {ranked.map((r) => {
          const p = perMap.get(r.peer.id)!;
          const disabled = p.blocker != null;
          const on = p.selected && !disabled;
          const open = expanded === r.peer.id;
          return (
            <Fragment key={r.peer.id}>
              <div className={`tr peer ${on ? "sel" : ""} ${disabled ? "dis" : ""}`}>
                <span className="cb-cell">
                  <input type="checkbox" className="cb" checked={on} disabled={disabled} onChange={() => toggle(r.peer.id)} aria-label={`${r.peer.name} 선택`} />
                  <button className="peer-name" onClick={() => setExpanded(open ? null : r.peer.id)} aria-expanded={open}>
                    <b>{r.peer.name} <i>{open ? "−" : "+"}</i></b>
                    <small>{r.peer.industry}{p.blocker ? ` · ${p.blocker}` : ""}</small>
                  </button>
                </span>
                {AREA_KEYS.map((k) => (<span key={k} className="score"><b>{(r.scores[k] as number).toFixed(0)}</b><u /></span>))}
                <span className="total mono">{(r.total as number).toFixed(1)}</span>
                <span className="mono">{x1(p.per)}</span>
                <span className="mono">{pct1(r.peer.evidence)}</span>
              </div>
              {open && (
                <div className="evidence">
                  <div className="card-head"><h3>{r.peer.name} · 선정 근거</h3><span className="small muted">근거 충족률 {pct1(r.peer.evidence)} · 검증 상태 {r.peer.status}</span></div>
                  <div className="grid2 tight">
                    {AREAS.map((a) => (
                      <article className="ev-card" key={a.key}>
                        <div className="row-between"><b>{a.label}</b><span className="mono blue">{(r.scores[a.key] as number).toFixed(1)} / 100</span></div>
                        <p>{evidenceText(a.key, r, s)}</p>
                        <div className="ev-compare">{evidenceCompare(a.key, r, target).map((c, i) => <span key={i}>{c}</span>)}</div>
                      </article>
                    ))}
                  </div>
                  <p className="small muted">원천 · {r.peer.source} · 기준일 {r.peer.date}{r.peer.memo ? ` · 검토 메모: ${r.peer.memo}` : ""}. 점수는 대상기업과의 유사도이며 투자 매력도가 아닙니다.</p>
                </div>
              )}
            </Fragment>
          );
        })}
      </div>
      <p className="small muted">기업명을 누르면 영역별 근거를 확인할 수 있습니다. 코사인 값은 외부 벡터 검색 결과를 입력받은 것이며, 이 화면은 점수·순위·PER만 계산합니다.</p>

      {excluded.length > 0 && (
        <button className="card excl" onClick={() => setShowExcl(!showExcl)} aria-expanded={showExcl}>
          기준 미충족 기업 {excluded.length}개 · 제외 사유 확인
          {showExcl && <div className="excl-body">{excluded.map((r) => <p key={r.peer.id}><b>{r.peer.name}</b> — {explainExclusion(r, s)}</p>)}</div>}
        </button>
      )}

      <section className="summary">
        <div><small>선택한 비교기업</small><div className="big mono">{included} 개</div></div>
        <div className="vr" />
        <div>
          <small>PER 범위 (Q1 – Q3)</small>
          <div className="big mono">{v.q1 != null ? `${v.q1.toFixed(1)} – ${v.q3!.toFixed(1)} 배` : "—"}</div>
        </div>
        <div className="sum-note">{v.q1 == null ? `최소 ${s.minPeers}개 이상 선택해야 합니다.` : `중앙값 ${v.median!.toFixed(1)}배`}</div>
        <button className="btn primary" disabled={v.q1 == null} onClick={onNext}>가치평가 결과 보기</button>
      </section>

      <Footer hint="선택을 바꾸면 PER 분포(Q1–Q3)가 즉시 갱신됩니다.">
        <button className="btn" onClick={onPrev}>이전 단계</button>
      </Footer>
    </Page>
  );
}

function evidenceText(k: string, r: RankRow, s: Settings): string {
  switch (k) {
    case "bm": return `제품·고객·수익구조·채널 텍스트를 같은 모델로 임베딩한 코사인 유사도 ${r.peer.bmCos?.toFixed(2)}를 100점 만점으로 환산했습니다.`;
    case "growth": return `매출 성장률 차이를 허용폭 ${(s.growthTol * 100).toFixed(0)}%p 기준으로 환산했습니다. 성장률이 높다는 이유로 점수가 오르지 않습니다.`;
    case "risk": return `규제·경쟁·고객집중·운영 위험 구조의 코사인 유사도 ${r.peer.riskCos?.toFixed(2)}입니다. 위험 수준이 같다는 뜻이 아니라 구조가 비슷하다는 뜻입니다.`;
    default: return `영업이익률과 부채/자산 비율의 근접도를 허용폭 ${(s.finTol * 100).toFixed(0)}%p 기준으로 평균했습니다.`;
  }
}

function evidenceCompare(k: string, r: RankRow, t: Company): string[] {
  const p = r.peer;
  switch (k) {
    case "bm": return [`BM 코사인 ${p.bmCos?.toFixed(2)}`, `산업 코사인 ${p.indCos?.toFixed(2)}`];
    case "growth": return [`대상 매출 성장 ${pct1(t.growth)}`, `비교 매출 성장 ${pct1(p.growth)}`];
    case "risk": return [`리스크 코사인 ${p.riskCos?.toFixed(2)}`];
    default: return [`대상 영업이익률 ${pct1(t.opMargin)} · 부채/자산 ${pct1(t.debtRatio)}`, `비교 ${pct1(p.opMargin)} · ${pct1(p.debtRatio)}`];
  }
}
