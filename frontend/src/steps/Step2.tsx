import { useState } from "react";
import { api } from "../api";
import { ErrorBox } from "../components/AsyncBoundary";
import { describeError } from "../api/errors";
import Loading from "../components/Loading";
import { PageHead } from "../components/Layout";
import { useResource } from "../hooks/useResource";
import type { BusinessProfile, CompanySummary } from "../types/domain";

interface Props { company: CompanySummary; onBack: () => void; onNext: () => void }

function ProfileView({ p }: { p: BusinessProfile }) {
  const [tab, setTab] = useState(0);
  const [open, setOpen] = useState<string | null>(null);
  const sec = p.sections[Math.min(tab, p.sections.length - 1)];
  const ev = new Map(p.evidence.map((e) => [e.id, e]));
  return (
    <>
      <section className="card">
        <div className="card-head pad">
          <div><h2>{p.companyName} Business Profile</h2>
            <small>{[p.industry, p.period, p.basis, p.version].filter(Boolean).join(" · ")}</small></div>
          {p.generatedAt && <small>생성 {p.generatedAt}</small>}
        </div>
        {p.summary && <p className="pad-x muted-d">{p.summary}</p>}
        <div className="tabs" role="tablist">
          {p.sections.map((s, i) => (
            <button key={s.key} role="tab" aria-selected={tab === i} className={`tab ${tab === i ? "on" : ""}`} onClick={() => { setTab(i); setOpen(null); }}>{s.label}</button>
          ))}
        </div>
        <div className="table profile">
          <div className="tr th"><span>항목</span><span>내용</span><span>근거</span></div>
          {sec.items.map((it) => (
            <div key={it.key}>
              <div className="tr">
                <span>{it.label}</span>
                <span className={`val ${it.value === "미확인" ? "muted" : ""}`}>{it.value}</span>
                <span>{it.evidenceIds.length > 0
                  ? <button className="link" aria-expanded={open === it.key} onClick={() => setOpen(open === it.key ? null : it.key)}>{open === it.key ? "닫기" : `보기 (${it.evidenceIds.length})`}</button>
                  : <span className="muted small">없음</span>}</span>
              </div>
              {open === it.key && (
                <div className="evi">
                  {it.evidenceIds.map((id) => {
                    const e = ev.get(id);
                    return e ? <div key={id}><b>{e.source}</b>{e.locator ? ` · ${e.locator}` : ""}{e.quote ? ` — “${e.quote}”` : ""}</div> : <div key={id}>근거 {id} (상세 없음)</div>;
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
      <div className="info-bar">이 Business Profile은 다음 단계에서 BGE-M3 임베딩과 언어네트워크를 결합(Late Fusion)해 유사기업 Top 5를 고르는 입력으로 쓰입니다.</div>
    </>
  );
}

export default function Step2({ company, onBack, onNext }: Props) {
  const res = useResource(`profile:${company.id}`, (s) => api.getProfile(company.id, s), (p: BusinessProfile) => p.sections.length === 0);
  const ready = res.status === "success" || res.status === "empty";
  return (
    <>
      {res.status === "loading" && <Loading title={`${company.name} 공시를 분석하는 중입니다`} onCancel={onBack} note="공시에서 Business Profile을 생성합니다." />}
      <PageHead step={1} eyebrow="PROFILE" title="Business Profile 확인" sub={`${company.name}의 공시 기반 사업 프로필입니다.`} />
      {res.status === "error" && res.error && <ErrorBox message={describeError(res.error)} onRetry={res.reload} label="프로필" />}
      {res.status === "empty" && <div className="empty">생성된 Business Profile이 없습니다. 공시 데이터가 있는지 확인해 주세요.</div>}
      {res.status === "success" && res.data && <ProfileView p={res.data} />}
      <div className="actions">
        <span className="hint">{ready ? "" : " "}</span>
        <div className="btns">
          <button className="btn" onClick={onBack}>이전</button>
          <button className="btn primary" disabled={res.status !== "success"} onClick={onNext}>유사기업 찾기</button>
        </div>
      </div>
    </>
  );
}
