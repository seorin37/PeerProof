import { useState } from "react";
import { AREAS, AREA_KEYS } from "../lib/areas";
import { keyLabel, profileValue } from "../lib/format";
import { RankRow, rankedOnly } from "../lib/engine";
import type { AreaKey, ProfileRow, Settings, Weights } from "../lib/types";
import { Footer, Page } from "../components/Layout";

interface Props {
  settings: Settings;
  profile: ProfileRow[];
  overrides: Record<string, string>;
  setOverride: (key: string, v: string) => void;
  pct: Weights;
  setPct: (w: Weights) => void;
  current: RankRow[];
  baseline: RankRow[];
  onPrev: () => void;
  onNext: () => void;
}

const TABS = [
  { label: "Business Model", area: "비즈니스" },
  { label: "Growth", area: "성장성" },
  { label: "Risk", area: "리스크" },
  { label: "Finance", area: "재무" },
  { label: "Evidence", area: "근거" },
];

export default function Step2({ settings: s, profile, overrides, setOverride, pct, setPct, current, baseline, onPrev, onNext }: Props) {
  const [tab, setTab] = useState(0);
  const [open, setOpen] = useState(true);
  const [evi, setEvi] = useState<string | null>(null);
  const [edit, setEdit] = useState<string | null>(null);
  const sum = AREA_KEYS.reduce((a, k) => a + pct[k], 0);
  const valid = sum === 100;
  const rows = profile.filter((r) => r.companyId === s.targetId && r.area === TABS[tab].area);
  const nowRank = rankedOnly(current);
  const baseRankMap = new Map(rankedOnly(baseline).map((r) => [r.peer.id, r.rank as number]));

  const setW = (k: AreaKey, v: number) => setPct({ ...pct, [k]: Math.max(0, Math.min(100, Math.round(v) || 0)) });

  return (
    <Page step={2} mode={s.mode} eyebrow="PROFILE & CRITERIA" title="프로필 확인, 비교 기준 설정" sub="대상기업의 비즈니스 프로필을 확인하고 네 영역의 가중치를 설정하세요.">
      <section className="card">
        <div className="card-head pad">
          <div>
            <h2>대상기업 비즈니스 프로필</h2>
            <div className="small muted">{s.period.replace("FY", "")}년 · {s.fsBasis === "CFS" ? "연결" : "별도"} · {s.currency} / 프로필 {s.profileVersion}{s.mode === "예시" ? " / 모든 값은 가상 예시" : ""}</div>
          </div>
          <button className="link" onClick={() => setOpen(!open)}>{open ? "접기" : "펼치기"}</button>
        </div>
        {open && (
          <>
            <div className="tabs" role="tablist">
              {TABS.map((t, i) => (
                <button key={t.label} role="tab" aria-selected={tab === i} className={`tab ${tab === i ? "on" : ""}`} onClick={() => { setTab(i); setEvi(null); setEdit(null); }}>{t.label}</button>
              ))}
            </div>
            <div className="table profile">
              <div className="tr th"><span>항목</span><span>값 · {s.mode === "예시" ? "가상 예시" : "추출값"}</span><span>근거 · 수정</span></div>
              {rows.map((r) => {
                const edited = overrides[r.key] !== undefined;
                const shown = edited ? overrides[r.key] : profileValue(r.key, r.value);
                return (
                  <div key={r.key}>
                    <div className="tr">
                      <span className="muted-d">{keyLabel(r.key)}</span>
                      {edit === r.key ? (
                        <input className="inline-edit" autoFocus defaultValue={shown} onBlur={(e) => { setOverride(r.key, e.target.value); setEdit(null); }} onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} />
                      ) : (
                        <b className="val">{shown}{edited && <em className="edited">수정됨</em>}</b>
                      )}
                      <span className="row-links">
                        <button className="link" onClick={() => setEvi(evi === r.key ? null : r.key)}>{evi === r.key ? "닫기" : "보기"}</button>
                        <button className="link" onClick={() => setEdit(r.key)}>수정</button>
                      </span>
                    </div>
                    {evi === r.key && (
                      <div className="evi">
                        근거 ID {r.evidenceId} · 추출 상태 <b>{r.extractStatus}</b> · 입력 상태 {r.inputStatus} · {r.period}<br />
                        정의 / 원문 위치: {r.definition} · 검토자 {r.reviewer}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="small muted pad-x">원자료와 계산값을 구분합니다. 근거가 없는 항목은 추정하지 않고 미확인으로 둡니다. 수정값은 프로필 기록에만 저장되며, 점수 재계산에는 외부 RAG 재실행이 필요합니다.</p>
          </>
        )}
      </section>

      <section className="card pad">
        <div className="card-head"><h2>영역별 가중치</h2><span className={`sumchip ${valid ? "ok" : "bad"}`}>합계 {sum}%</span></div>
        <p className="small muted">네 영역의 합계가 100%여야 점수가 산출됩니다. 자동으로 정규화하지 않습니다. 가중치를 바꿔도 RAG 재검색은 필요하지 않습니다.</p>
        <div className="imp-list">
          {AREAS.map((a) => (
            <div className="imp" key={a.key}>
              <div className="imp-name" style={{ borderColor: a.color }}>
                <b>{a.label}</b><span className="small muted">{a.desc}</span>
              </div>
              <div className="wctl">
                <input type="range" min={0} max={100} step={5} value={pct[a.key]} onChange={(e) => setW(a.key, Number(e.target.value))} aria-label={`${a.label} 가중치`} style={{ accentColor: "#2762e7" }} />
                <span className="input num"><input inputMode="numeric" value={pct[a.key]} onChange={(e) => setW(a.key, Number(e.target.value.replace(/\D/g, "")))} /><em>%</em></span>
              </div>
              <div className="imp-pct mono" style={{ color: a.color }}>{pct[a.key]}%</div>
            </div>
          ))}
        </div>
        {!valid && <div className="warn">가중치 합계가 {sum}%입니다. 합계를 100%로 맞춰야 다음 단계로 진행할 수 있습니다.</div>}
      </section>

      <section className="card pad">
        <div className="card-head"><h2>예상 순위 변화</h2><span className="muted small">파일 기본 가중치 대비</span></div>
        {valid ? (
          <div className="table rankchg">
            <div className="tr th"><span>기업</span><span>현재 순위</span><span>기본 순위</span><span>변화</span><span>종합유사도</span></div>
            {nowRank.map((r) => {
              const before = baseRankMap.get(r.peer.id);
              const d = before != null && r.rank != null ? before - r.rank : 0;
              return (
                <div className="tr" key={r.peer.id}>
                  <span>{r.peer.name}</span><span className="mono">{r.rank}</span><span className="mono">{before ?? "—"}</span>
                  <span className={`mono ${d > 0 ? "up" : d < 0 ? "down" : ""}`}>{d > 0 ? `▲ ${d}` : d < 0 ? `▼ ${-d}` : "–"}</span>
                  <span className="mono blue">{(r.total as number).toFixed(1)}</span>
                </div>
              );
            })}
          </div>
        ) : (<div className="empty">합계가 100%가 되면 예상 순위가 표시됩니다.</div>)}
      </section>

      <div className="info-bar">유사도는 대상기업과 비교기업의 비슷한 특성을 나타내며 투자 매력도가 아닙니다. 가중치는 비교기업 선정에만 적용되고, 최종 평가에는 선택 기업의 PER 분포(Q1–Q3)를 사용합니다.</div>

      <Footer hint={`${s.targetName} / ${s.industry}`}>
        <button className="btn" onClick={onPrev}>이전 단계</button>
        <button className="btn primary" disabled={!valid} onClick={onNext}>비교기업 탐색</button>
      </Footer>
    </Page>
  );
}
