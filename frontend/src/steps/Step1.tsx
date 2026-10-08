import { ChangeEvent, useRef, useState } from "react";
import type { Company, Settings } from "../lib/types";
import { Footer, Page } from "../components/Layout";

interface Props {
  settings: Settings;
  companies: Company[];
  fileName: string;
  fileError: string | null;
  industry: string;
  setIndustry: (i: string) => void;
  company: boolean;
  setCompany: (v: boolean) => void;
  onFile: (f: File) => void;
  onNext: () => void;
}

export default function Step1({ settings: s, companies, fileName, fileError, industry, setIndustry, company, setCompany, onFile, onNext }: Props) {
  const [q, setQ] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const industries = Array.from(new Set(companies.map((c) => c.industry)));
  const matches = s.industry === industry && (q.trim() === "" || (s.targetName + s.industry).includes(q.trim()));
  const basis = [
    ["평가기준일", s.asOf], ["이익 비교기간", s.period], ["통화", s.currency], ["재무제표 기준", s.fsBasis === "CFS" ? "CFS 연결" : s.fsBasis === "OFS" ? "OFS 별도" : s.fsBasis],
  ];
  const pick = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) onFile(f);
    e.target.value = "";
  };

  return (
    <Page step={1} mode={s.mode} eyebrow="TARGET COMPANY" title="비교의 시작, 대상기업 선택" sub="산업을 선택하고 분석할 IPO 기업을 지정하세요.">
      <section className="card pad">
        <div className="card-head"><h2>01 &nbsp;산업 선택</h2><span className="muted">한국 시장</span></div>
        <div className="grid2">
          {industries.map((name, i) => (
            <button key={name} className={`choice ${industry === name ? "on" : ""}`} onClick={() => { setIndustry(name); setCompany(false); }}>
              <span className="mono">{String(i + 1).padStart(2, "0")}</span>{name}
              {industry === name && <span className="tick">✓</span>}
            </button>
          ))}
        </div>

        <hr className="rule" />
        <div className="card-head"><h2>02 &nbsp;IPO 후보기업</h2><span className="muted">데이터 연결 전</span></div>
        <label className="input search">
          <span className="ico">⌕</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="기업명 또는 산업 검색" />
        </label>
        <div className="row-between small muted"><span>실제 IPO 후보 0개</span><span>체험용 프로필 {matches ? 1 : 0}개</span></div>
        {matches ? (
          <button className={`choice wide ${company ? "on" : ""}`} onClick={() => setCompany(!company)} aria-pressed={company}>
            <span className="mono">01</span><b>{s.targetName}</b><span className="sep">·</span><span>{s.industry}</span>
            <span className="gap" /><span className="mono">{s.targetId}</span><span>{s.mode === "예시" ? "체험용" : "확정"}</span>
            {company && <span className="tick">✓</span>}
          </button>
        ) : (
          <div className="empty">조건에 맞는 체험용 프로필이 없습니다. 「{s.industry}」 산업을 선택해 보세요.</div>
        )}
        <p className="note">실제 기업 목록은 아직 등록되지 않았습니다.<br />체험용 프로필을 선택하면 전체 평가 흐름을 확인할 수 있습니다.</p>

        <hr className="rule" />
        <div className="card-head"><h2>03 &nbsp;분석 기준 · 데이터</h2><span className="muted">대상·분석 범위 고정</span></div>
        <div className="basis">
          {basis.map(([k, v]) => (<div key={k}><small>{k}</small><b className="mono">{v}</b></div>))}
        </div>
        <div className="source">
          <div><small>데이터 파일</small><b className="mono">{fileName}</b><span className="badge">{s.mode} 모드</span></div>
          <input ref={fileRef} type="file" accept=".xlsx" hidden onChange={pick} />
          <button className="btn slim" onClick={() => fileRef.current?.click()}>엑셀 불러오기</button>
        </div>
        {fileError && <div className="warn">{fileError}</div>}
        <p className="note">01_입력설정 · 05_기업입력 · 06_프로필근거 시트를 읽어 화면을 구성합니다. 유사도 점수와 PER 밴드는 이 화면에서 엑셀과 같은 수식으로 계산합니다.</p>
      </section>
      <Footer hint="선택한 기업의 산업 1차 필터와 비즈니스 프로필 분석을 실행합니다.">
        <button className="btn primary" disabled={!company} onClick={onNext}>대상기업 분석</button>
      </Footer>
    </Page>
  );
}
