import { ReactNode } from "react";
import type { Mode } from "../lib/types";

export const STEPS = [
  { no: "01", ko: "대상기업 선택", en: "TARGET COMPANY", pipe: "PIPELINE 01–02" },
  { no: "02", ko: "프로필·중요도 설정", en: "PROFILE & CRITERIA", pipe: "PIPELINE 03–04" },
  { no: "03", ko: "비교기업 검토", en: "PEER SELECTION", pipe: "PIPELINE 05–07" },
  { no: "04", ko: "가치평가 결과", en: "VALUATION RESULT", pipe: "PIPELINE 08" },
];

export function Header({ mode }: { mode: Mode }) {
  return (
    <header className="header">
      <div className="logo">
        <span className="logo-mark">P</span>
        <span className="logo-word">PEER PROOF</span>
      </div>
      <nav className="header-nav">
        <a className="on" href="#">IPO 상대가치평가</a>
        <a href="#">평가 방법론</a>
      </nav>
      <div className="header-right">
        <span className="market">KR 한국 시장</span>
        <span className={`chip-demo ${mode === "확정" ? "confirmed" : ""}`}>
          {mode === "예시" ? "DEMO WORKSPACE" : "CONFIRMED MODE"}
        </span>
      </div>
    </header>
  );
}

export function Sidebar({ step, onGo }: { step: number; onGo: (s: number) => void }) {
  return (
    <aside className="sidebar">
      <div className="side-label">VALUATION WORKSPACE</div>
      <ol className="side-steps">
        {STEPS.map((s, i) => {
          const n = i + 1;
          const done = n < step;
          return (
            <li key={s.no}>
              <button
                className={`side-step ${n === step ? "active" : ""} ${done ? "done" : ""}`}
                disabled={n > step}
                onClick={() => onGo(n)}
                aria-current={n === step ? "step" : undefined}
              >
                <span className="side-no">{done ? "✓" : s.no}</span>
                <span>
                  <span className="side-ko">{s.ko}</span>
                  <span className="side-en">{s.en}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      <div className="side-foot">
        <div className="side-label">VALUATION FRAMEWORK</div>
        <div className="serif">Fundamentals first.</div>
        <p>사업 · 성장 · 위험 · 재무<br />근거로 연결되는 상대가치평가</p>
        <a href="#" className="side-link">방법론 살펴보기 <span>↗</span></a>
        <div className="side-ver"><span>PEER PROOF</span><span>V.01</span></div>
      </div>
    </aside>
  );
}

export function Page({
  step, mode, eyebrow, title, sub, children,
}: { step: number; mode: Mode; eyebrow: string; title: string; sub: string; children: ReactNode }) {
  return (
    <main className="main">
      <div className="crumb">
        <span>Workspace <i>/</i> 신규 IPO 평가</span>
        <span>{mode === "예시" ? "가상 시나리오" : "확정 입력"} <b className="dot" /></span>
      </div>
      <div className="demo-banner">
        {mode === "예시" ? (
          <><b>DEMO</b> 실제 IPO 데이터가 없는 예시 모드입니다. 기업·수치·유사도·설명은 모두 가상 예시입니다.</>
        ) : (
          <><b>확정</b> 확정 모드입니다. 근거·재무·대상기업 입력 상태가 모두 확정인 경우에만 점수와 밴드가 산출됩니다.</>
        )}
      </div>
      <div className="page-head">
        <div>
          <div className="eyebrow">{eyebrow} <span className="pipe">/ {STEPS[step - 1].pipe}</span></div>
          <h1>{title}</h1>
          <p className="sub">{sub}</p>
        </div>
        <div className="step-no">STEP {String(step).padStart(2, "0")} / 04</div>
      </div>
      {children}
    </main>
  );
}

export function Footer({ hint, children }: { hint: string; children?: ReactNode }) {
  return (
    <>
      <div className="actions">
        <span className="hint">{hint}</span>
        <div className="btns">{children}</div>
      </div>
      <div className="foot">
        <span>PEER PROOF <i>/</i> 근거 중심의 비교기업 선정</span>
        <span>대한민국 · KRW</span>
      </div>
    </>
  );
}
