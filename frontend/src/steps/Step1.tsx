import { useEffect, useMemo, useState } from "react";
import { api, API_MODE } from "../api";
import AsyncBoundary from "../components/AsyncBoundary";
import { PageHead } from "../components/Layout";
import { useResource } from "../hooks/useResource";
import type { CompanySummary } from "../types/domain";

interface Props { selected: CompanySummary | null; onSelect: (c: CompanySummary) => void; onNext: () => void }

const SECTOR_ORDER = ["반도체·전자", "소프트웨어·IT", "바이오·헬스케어", "에너지·소재"];
const pad = (n: number) => String(n).padStart(2, "0");

export default function Step1({ selected, onSelect, onNext }: Props) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [sector, setSector] = useState<string | null>(null);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 250);
    return () => clearTimeout(t);
  }, [query]);

  // 산업 칩은 전체 목록(검색어 없음)에서 만듭니다. 백엔드가 sector를 주지 않으면 이 영역은 숨겨집니다.
  const all = useResource<CompanySummary[]>("companies:", (s) => api.searchCompanies("", s), (d) => d.length === 0);
  const sectors = useMemo(() => {
    const found = Array.from(new Set((all.data ?? []).map((c) => c.sector).filter((x): x is string => !!x)));
    return [...SECTOR_ORDER.filter((s) => found.includes(s)), ...found.filter((s) => !SECTOR_ORDER.includes(s))];
  }, [all.data]);

  const res = useResource<CompanySummary[]>(`companies:${debounced}`, (s) => api.searchCompanies(debounced, s), (d) => d.length === 0);
  const filtered = (res.data ?? []).filter((c) => !sector || c.sector === sector);

  return (
    <>
      <PageHead step={0} eyebrow="TARGET COMPANY" title="비교의 시작, 대상기업 선택" sub="산업을 선택하고 분석할 IPO 기업을 지정하세요." />
      <section className="card pad">
        {sectors.length > 0 && (
          <>
            <div className="row-between"><h2>01 &nbsp;산업 선택</h2><small>한국 시장</small></div>
            <div className="grid2" style={{ marginTop: 16 }}>
              {sectors.map((s, i) => (
                <button key={s} className={`choice ${sector === s ? "on" : ""}`} aria-pressed={sector === s} onClick={() => setSector(sector === s ? null : s)}>
                  <span className="mono">{pad(i + 1)}</span><span>{s}</span>{sector === s && <span className="tick">✓</span>}
                </button>
              ))}
            </div>
            <hr className="rule" />
          </>
        )}
        <div className="row-between">
          <h2>{sectors.length > 0 ? "02 " : ""}&nbsp;IPO 후보기업</h2>
          <small>{API_MODE === "live" ? "백엔드 연결됨" : "데이터 연결 전 · MOCK"}</small>
        </div>
        <label className="input search" style={{ marginTop: 16 }}>
          <span className="ico" aria-hidden>⌕</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="기업명 또는 산업 검색" aria-label="기업 검색" />
        </label>
        <div className="row-between"><small>{res.status === "success" ? `후보 ${filtered.length}개` : ""}</small><small>{API_MODE === "mock" ? "체험용 프로필" : ""}</small></div>
        <AsyncBoundary res={res} rows={4} label="기업 목록" emptyText={debounced ? `‘${debounced}’에 해당하는 기업이 없습니다.` : "표시할 기업이 없습니다."}>
          {() => filtered.length === 0 ? <div className="empty">이 산업에 해당하는 후보기업이 없습니다.</div> : (
            <div role="listbox" aria-label="IPO 후보기업">
              {filtered.map((c, i) => (
                <button key={c.id} role="option" aria-selected={selected?.id === c.id}
                  className={`choice wide ${selected?.id === c.id ? "on" : ""}`} onClick={() => onSelect(c)}>
                  <span className="mono">{pad(i + 1)}</span>
                  <b>{c.name}</b>
                  <span className="muted small">· {[c.industry, c.market].filter(Boolean).join(" · ")}</span>
                  {selected?.id === c.id && <span className="tick">✓</span>}
                </button>
              ))}
            </div>
          )}
        </AsyncBoundary>
        <p className="note">후보 목록은 {API_MODE === "mock" ? "예시(가상) 기업입니다. 체험용 프로필을 선택하면 전체 평가 흐름을 확인할 수 있습니다." : "백엔드에서 불러온 IPO 후보입니다."}</p>
      </section>
      <div className="actions">
        <span className="hint">{selected ? `선택: ${selected.name}` : "선택한 기업의 비즈니스 프로필을 분석합니다."}</span>
        <div className="btns"><button className="btn primary" disabled={!selected} onClick={onNext}>대상기업 분석</button></div>
      </div>
    </>
  );
}
