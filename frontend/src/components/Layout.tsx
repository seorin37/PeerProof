import type { ReactNode } from "react";
import { API_MODE } from "../api";

export const STEPS = [
  { ko: "대상기업 선택", en: "TARGET COMPANY" },
  { ko: "프로필·중요도 설정", en: "PROFILE & CRITERIA" },
  { ko: "비교기업 검토", en: "PEER SELECTION" },
  { ko: "가치평가 결과", en: "VALUATION RESULT" },
];

export function Header() {
  return (
    <header className="header">
      <div className="logo">
        <span className="logo-mark">P</span>
        <span className="logo-word">PEER PROOF</span>
      </div>
      <nav className="header-nav"><a className="on" href="/">IPO 상대가치평가</a><a href="/">평가 방법론</a></nav>
      <div className="header-right">
        <span className="market">KR &nbsp;한국 시장</span>
      </div>
    </header>
  );
}
interface SidebarProps { step: number; maxStep: number; onGo: (s: number) => void }

export function Sidebar({ step, maxStep, onGo }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="side-label">VALUATION WORKSPACE</div>
      <ol className="side-steps">
        {STEPS.map((s, i) => (
          <li key={s.en}>
            <button
              className={`side-step ${step === i ? "active" : ""} ${i < step ? "done" : ""}`}
              disabled={i > maxStep}
              aria-current={step === i ? "step" : undefined}
              onClick={() => onGo(i)}
            >
              <span className="side-no">{i < step ? "✓" : String(i + 1).padStart(2, "0")}</span>
              <span><span className="side-ko">{s.ko}</span><span className="side-en">{s.en}</span></span>
            </button>
          </li>
        ))}
      </ol>
      <div className="side-foot">
        <small className="side-label">VALUATION FRAMEWORK</small>
        <div className="serif">Fundamentals first.</div>
        <p>사업 · 성장 · 위험 · 재무<br />근거로 연결되는 상대가치평가</p>
        <a className="side-link" href="/">방법론 살펴보기 ↗</a>
        <div className="side-ver"><span>PEER PROOF</span><span>V.01</span></div>
      </div>
    </aside>
  );
}

export function ModeBanner() {
  if (API_MODE === "live") return null;
  return (
    <div className="demo-banner">
      실제 IPO 데이터가 없는 체험용 화면입니다. 기업·수치·유사도·설명은 모두 가상 예시입니다.
    </div>
  );
}

export function PageHead({ step, eyebrow, title, sub }: { step: number; eyebrow: string; title: string; sub?: ReactNode }) {
  return (
    <>
      <div className="crumb">
        <span>Workspace <i>/</i> 신규 IPO 평가</span>
        <span>{API_MODE === "live" ? "실제 데이터" : "가상 시나리오"}<span className="dot" /></span>
      </div>
      <ModeBanner />
      <div className="page-head">
        <div>
          <div className="eyebrow">{eyebrow}</div>
          <h1>{title}</h1>
          {sub && <p className="sub">{sub}</p>}
        </div>
        <div className="step-no">STEP {String(step + 1).padStart(2, "0")} / {String(STEPS.length).padStart(2, "0")}</div>
      </div>
    </>
  );
}

export function Footer() {
  return (
    <footer className="foot">
      <span>PEER PROOF / 근거 중심의 비교기업 선정</span>
      <span>대한민국 · KRW</span>
    </footer>
  );
}
