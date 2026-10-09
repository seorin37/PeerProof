import { useState } from "react";
import { clearResourceCache } from "./hooks/useResource";
import { Footer, Header, Sidebar } from "./components/Layout";
import Step1 from "./steps/Step1";
import Step2 from "./steps/Step2";
import Step3 from "./steps/Step3";
import Step4 from "./steps/Step4";
import type { CompanySummary } from "./types/domain";

export default function App() {
  const [step, setStep] = useState(0);
  const [maxStep, setMaxStep] = useState(0);
  const [company, setCompany] = useState<CompanySummary | null>(null);
  /** Step3 체크박스로 고른 비교기업 id. null이면 아직 고르지 않음(기본값 사용) */
  const [picked, setPicked] = useState<string[] | null>(null);

  const go = (s: number) => { setStep(s); setMaxStep((m) => Math.max(m, s)); window.scrollTo(0, 0); };
  const pick = (c: CompanySummary) => { setCompany(c); setPicked(null); setMaxStep(0); };
  const reset = () => { clearResourceCache(); setCompany(null); setPicked(null); setStep(0); setMaxStep(0); window.scrollTo(0, 0); };

  return (
    <>
      <Header />
      <div className="shell">
        <Sidebar step={step} maxStep={company ? maxStep : 0} onGo={setStep} />
        <main className="main">
          {step === 0 && <Step1 selected={company} onSelect={pick} onNext={() => go(1)} />}
          {step === 1 && company && <Step2 company={company} onBack={() => go(0)} onNext={() => go(2)} />}
          {step === 2 && company && <Step3 company={company} picked={picked} onBack={() => go(1)} onNext={(ids) => { setPicked(ids); go(3); }} />}
          {step === 3 && company && <Step4 company={company} picked={picked} onBack={() => go(2)} onReset={reset} />}
          <Footer />
        </main>
      </div>
    </>
  );
}
