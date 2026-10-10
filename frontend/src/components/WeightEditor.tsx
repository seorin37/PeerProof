import { AREAS, LEVEL_LABELS, levelSum, toPercents, type Levels } from "../lib/scoring";

interface Props { levels: Levels; onChange: (l: Levels) => void; note?: string }

/** 영역별 중요도(0–4단계) 선택. 단계 합계로 나눈 비중(%)을 오른쪽에 표시합니다. */
export default function WeightEditor({ levels, onChange, note }: Props) {
  const pct = toPercents(levels);
  return (
    <section className="card pad">
      <div className="card-head">
        <div><h2>영역별 중요도</h2><p className="sub">선택한 중요도를 합계로 나누어 비교 비중으로 자동 환산합니다.</p></div>
        <small>0–4 단계</small>
      </div>
      <div className="imp-list">
        {AREAS.map((a) => (
          <div className="imp" key={a.key}>
            <div className="imp-name" style={{ borderColor: a.color }}><b>{a.label}</b><small>{a.hint}</small></div>
            <div className="seg" role="radiogroup" aria-label={`${a.label} 중요도`}>
              {LEVEL_LABELS.map((lb, i) => (
                <button key={i} role="radio" aria-checked={levels[a.key] === i} className={levels[a.key] === i ? "on" : ""}
                  onClick={() => onChange({ ...levels, [a.key]: i })}>{i}<b>{lb}</b></button>
              ))}
            </div>
            <div className="imp-pct mono" style={{ color: a.color }}>{Math.round(pct[a.key])}%</div>
          </div>
        ))}
      </div>
      {levelSum(levels) === 0 && <div className="warn" role="alert">하나 이상의 영역을 0단계보다 높게 설정해 주세요.</div>}
      {note && <p className="note">{note}</p>}
    </section>
  );
}
