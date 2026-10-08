import { useCallback, useEffect, useMemo, useState } from "react";
import { Header, Sidebar } from "./components/Layout";
import Loading from "./components/Loading";
import Step1 from "./steps/Step1";
import Step2 from "./steps/Step2";
import Step3 from "./steps/Step3";
import Step4 from "./steps/Step4";
import { AREA_KEYS } from "./lib/areas";
import { buildPerRows, rankPeers, valuate } from "./lib/engine";
import type { ParsedData, Settings, Weights } from "./lib/types";
import { parseWorkbook } from "./lib/workbook";

const toPct = (w: Weights): Weights => {
  const o = {} as Weights;
  AREA_KEYS.forEach((k) => (o[k] = Math.round(w[k] * 100)));
  return o;
};
const toFrac = (p: Weights): Weights => {
  const o = {} as Weights;
  AREA_KEYS.forEach((k) => (o[k] = p[k] / 100));
  return o;
};

export default function App() {
  const [data, setData] = useState<ParsedData | null>(null);
  const [fileName, setFileName] = useState("sample.xlsx");
  const [fileError, setFileError] = useState<string | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);

  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [industry, setIndustry] = useState("");
  const [company, setCompany] = useState(true);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [pct, setPct] = useState<Weights | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [overrides, setOverrides] = useState<Record<string, string>>({});

  const apply = useCallback((d: ParsedData, name: string) => {
    setData(d);
    setFileName(name);
    setSettings(d.settings);
    setPct(toPct(d.settings.weights));
    setSelected(d.perInputs.filter((p) => p.selected).map((p) => p.id));
    setIndustry(d.settings.industry);
    setCompany(true);
    setOverrides({});
    setStep(1);
  }, []);

  // 기본 데이터: public/sample.xlsx (실서비스에서는 API 응답을 parse 대신 바로 ParsedData 로 주입)
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}sample.xlsx`)
      .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error("sample.xlsx를 불러오지 못했습니다."))))
      .then((buf) => apply(parseWorkbook(buf), "sample.xlsx"))
      .catch((e: Error) => setFatal(e.message));
  }, [apply]);

  const onFile = async (f: File) => {
    try {
      apply(parseWorkbook(await f.arrayBuffer()), f.name);
      setFileError(null);
    } catch (e) {
      setFileError((e as Error).message);
    }
  };

  const model = useMemo(() => {
    if (!data || !settings || !pct) return null;
    const target = data.companies.find((c) => c.id === settings.targetId)!;
    const peers = data.companies.filter((c) => c.id !== settings.targetId);
    const rows = rankPeers(settings, target, peers, toFrac(pct));
    const baseline = rankPeers(settings, target, peers, data.settings.weights);
    const perRows = buildPerRows(settings, rows, data.perInputs, selected);
    return { target, rows, baseline, perRows, valuation: valuate(settings, perRows) };
  }, [data, settings, pct, selected]);

  if (fatal) return <div className="boot">{fatal}</div>;
  if (!data || !settings || !pct || !model) return <div className="boot">데이터를 불러오는 중…</div>;

  const go = (s: number) => { setStep(s); window.scrollTo({ top: 0 }); };
  const reset = () => apply(data, fileName);

  if (loading)
    return <Loading candidates={model.rows.filter((r) => r.pass1).length} onDone={() => { setLoading(false); go(2); }} />;

  return (
    <div className="app">
      <Header mode={settings.mode} />
      <div className="shell">
        <Sidebar step={step} onGo={go} />
        {step === 1 && (
          <Step1 settings={settings} companies={data.companies} fileName={fileName} fileError={fileError} industry={industry}
            setIndustry={setIndustry} company={company} setCompany={setCompany} onFile={onFile} onNext={() => setLoading(true)} />
        )}
        {step === 2 && (
          <Step2 settings={settings} profile={data.profile} overrides={overrides} setOverride={(k, v) => setOverrides({ ...overrides, [k]: v })}
            pct={pct} setPct={setPct} current={model.rows} baseline={model.baseline} onPrev={() => go(1)} onNext={() => go(3)} />
        )}
        {step === 3 && (
          <Step3 settings={settings} target={model.target} setSettings={setSettings} pct={pct} rows={model.rows} perRows={model.perRows}
            valuation={model.valuation} selectedIds={selected} setSelected={setSelected} onPrev={() => go(2)} onNext={() => go(4)} onAdjust={() => go(2)} />
        )}
        {step === 4 && (
          <Step4 settings={settings} setSettings={setSettings} rows={model.rows} perRows={model.perRows} valuation={model.valuation}
            onPrev={() => go(3)} onReset={reset} />
        )}
      </div>
    </div>
  );
}
