import { api } from "../api";
import AsyncBoundary from "../components/AsyncBoundary";
import { PageHead } from "../components/Layout";
import { deriveStats } from "../lib/network";
import { useResource } from "../hooks/useResource";
import type { CompanySummary, MetricDef, MetricRow, MetricsTable } from "../types/domain";

interface Props { company: CompanySummary; picked: string[] | null; onBack: () => void; onReset: () => void }

const fmt = (n: number | null | undefined, unit = "%") => (n === null || n === undefined ? "—" : `${n.toFixed(1)}${unit}`);

/** 체크한 기업만 남긴다. 고른 적이 없으면(null) 후보 전체. 대상기업은 항상 포함. */
function choose(t: MetricsTable, picked: string[] | null): { target: MetricRow | undefined; peers: MetricRow[] } {
  const set = picked === null ? null : new Set(picked);
  return {
    target: t.rows.find((r) => r.isTarget),
    peers: t.rows.filter((r) => !r.isTarget && (set === null || set.has(r.companyId))),
  };
}

function summary(peers: MetricRow[], m: MetricDef) {
  const values = peers.map((p) => p.values[m.key]).filter((v): v is number => v !== null && v !== undefined);
  return { n: values.length, ...(deriveStats(values) ?? { min: null, median: null, max: null }) };
}

function position(target: number | null | undefined, median: number | null): string {
  if (target === null || target === undefined || median === null) return "비교 불가";
  const d = target - median;
  return `${d >= 0 ? "+" : ""}${d.toFixed(1)}%p vs 중앙값`;
}

function Result({ t, picked }: { t: MetricsTable; picked: string[] | null }) {
  const { target, peers } = choose(t, picked);
  const cols = { gridTemplateColumns: `1.6fr repeat(${t.metrics.length}, 1fr)` };
  const stats = t.metrics.map((m) => ({ m, s: summary(peers, m) }));
  return (
    <>
      <section className="card pad kpis metric-kpis">
        {stats.map(({ m, s }) => (
          <div key={m.key}>
            <small>{m.label}</small>
            <div className="mono">{fmt(target?.values[m.key], m.unit)}</div>
            <small className="muted">비교기업 중앙값 {fmt(s.median, m.unit)} · {position(target?.values[m.key], s.median)}</small>
          </div>
        ))}
      </section>
      <section className="card">
        <div className="card-head pad"><h2>비교기업 재무 지표 ({peers.length}곳)</h2><small>{t.basis ?? ""}</small></div>
        <div className="table mtable">
          <div className="tr th" style={cols}><span>기업</span>{t.metrics.map((m) => <span key={m.key} title={m.note}>{m.label}</span>)}</div>
          {target && (
            <div className="tr target-row" style={cols}>
              <span><b>{target.name}</b><small className="muted"> 대상 · {target.period ?? ""}</small></span>
              {t.metrics.map((m) => <span key={m.key} className="mono">{fmt(target.values[m.key], m.unit)}</span>)}
            </div>
          )}
          {peers.map((p) => (
            <div className="tr" key={p.companyId} style={cols}>
              <span>{p.sourceUrl ? <a href={p.sourceUrl} target="_blank" rel="noreferrer">{p.name}</a> : p.name}<small className="muted"> {p.period ?? ""}</small></span>
              {t.metrics.map((m) => <span key={m.key} className="mono">{fmt(p.values[m.key], m.unit)}</span>)}
            </div>
          ))}
          {(["min", "median", "max"] as const).map((k) => (
            <div className="tr stat-row" key={k} style={cols}>
              <span><b>{k === "min" ? "최소" : k === "median" ? "중앙값" : "최대"}</b></span>
              {stats.map(({ m, s }) => <span key={m.key} className="mono">{fmt(s[k], m.unit)}</span>)}
            </div>
          ))}
        </div>
      </section>
      {t.notes.map((n, i) => <div className="info-bar" key={i}>{n}</div>)}
    </>
  );
}

export default function Step4({ company, picked, onBack, onReset }: Props) {
  const res = useResource(`metrics:${company.id}`, (s) => api.getMetrics(company.id, s), (v: MetricsTable) => v.rows.length === 0);
  return (
    <>
      <PageHead step={3} eyebrow="FINANCIAL COMPARISON" title="재무 지표 비교" sub={`${company.name}과(와) 선택한 비교기업의 DART 공시 기반 재무 지표입니다.`} />
      <AsyncBoundary res={res} rows={6} label="재무 지표" emptyText="비교에 사용할 수 있는 재무 데이터가 없습니다.">
        {(t) => <Result t={t} picked={picked} />}
      </AsyncBoundary>
      <div className="actions">
        <span />
        <div className="btns"><button className="btn" onClick={onBack}>이전</button><button className="btn primary" onClick={onReset}>새 분석 시작</button></div>
      </div>
    </>
  );
}
