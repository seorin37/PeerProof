import { useState } from "react";
import { api } from "../api";
import { describeError } from "../api/errors";
import { ErrorBox } from "../components/AsyncBoundary";
import { PageHead } from "../components/Layout";
import Loading from "../components/Loading";
import WeightEditor from "../components/WeightEditor";
import { useResource } from "../hooks/useResource";
import { levelSum, type Levels } from "../lib/scoring";
import type { BusinessProfile, CompanySummary } from "../types/domain";

interface Props {
  company: CompanySummary; levels: Levels; onLevels: (l: Levels) => void; onBack: () => void; onNext: () => void;
}

function ProfileCard({ p }: { p: BusinessProfile }) {
  const [tab, setTab] = useState(0);
  const [open, setOpen] = useState<string | null>(null);
  const [folded, setFolded] = useState(false);
  const sec = p.sections[Math.min(tab, p.sections.length - 1)];
  const ev = new Map(p.evidence.map((e) => [e.id, e]));
  return (
    <section className="card">
      <div className="card-head pad">
        <div><h2>대상기업 비즈니스 프로필</h2>
          <small>{[p.period, p.basis, p.version].filter(Boolean).join(" · ")}</small></div>
        <button className="link" aria-expanded={!folded} onClick={() => setFolded(!folded)}>{folded ? "펼치기" : "접기"}</button>
      </div>
      {!folded && (
        <>
          {p.summary && <p className="pad-x muted-d small">{p.summary}</p>}
          <div className="tabs" role="tablist">
            {p.sections.map((s, i) => (
              <button key={s.key} role="tab" aria-selected={tab === i} className={`tab ${tab === i ? "on" : ""}`} onClick={() => { setTab(i); setOpen(null); }}>{s.label}</button>
            ))}
          </div>
          <div className="table profile">
            <div className="tr th"><span>항목</span><span>값</span><span>근거</span></div>
            {sec.items.map((it) => (
              <div key={it.key}>
                <div className="tr">
                  <span>{it.label}</span>
                  <span className={`val ${it.value === "미확인" ? "muted" : ""}`}>{it.value}</span>
                  <span>{it.evidenceIds.length > 0
                    ? <button className="link" aria-expanded={open === it.key} onClick={() => setOpen(open === it.key ? null : it.key)}>{open === it.key ? "닫기" : "보기"}</button>
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
          <p className="note pad-x">원자료와 계산값을 구분합니다. 보고서명·접수일·섹션·링크는 각 항목의 근거에서 확인할 수 있습니다.</p>
        </>
      )}
    </section>
  );
}

export default function Step2({ company, levels, onLevels, onBack, onNext }: Props) {
  const res = useResource(`profile:${company.id}`, (s) => api.getProfile(company.id, s), (p: BusinessProfile) => p.sections.length === 0);
  return (
    <>
      {res.status === "loading" && <Loading title={`${company.name} 공시를 분석하는 중입니다`} onCancel={onBack} note="공시에서 Business Profile을 생성합니다." />}
      <PageHead step={1} eyebrow="PROFILE & CRITERIA" title="프로필 확인, 비교 기준 설정" sub="대상기업의 비즈니스 프로필을 확인하고 네 영역의 중요도를 설정하세요." />
      {res.status === "error" && res.error && <ErrorBox message={describeError(res.error)} onRetry={res.reload} label="프로필" />}
      {res.status === "empty" && <div className="empty">생성된 Business Profile이 없습니다. 공시 데이터가 있는지 확인해 주세요.</div>}
      {res.status === "success" && res.data && <ProfileCard p={res.data} />}
      <WeightEditor levels={levels} onChange={onLevels} />
      <div className="info-bar">유사도는 대상기업과 비교기업의 비슷한 특성을 나타냅니다. 중요도는 영역별 임베딩 유사도의 비중으로 적용되어 언어네트워크 점수와 Late Fusion으로 결합되며, 최종 평가에는 선택 기업의 PER 산술평균을 사용합니다.</div>
      <div className="actions">
        <span className="hint">{[company.name, company.sector ?? company.industry].filter(Boolean).join(" / ")}</span>
        <div className="btns">
          <button className="btn" onClick={onBack}>이전 단계</button>
          <button className="btn primary" disabled={res.status !== "success" || levelSum(levels) === 0} onClick={onNext}>비교기업 탐색</button>
        </div>
      </div>
    </>
  );
}
