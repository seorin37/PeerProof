interface Props {
  value: number | null;
  tone?: "main" | "sub";
  label?: string;
}

/** 0–100 점수를 막대로 표시. 값이 없으면 '—' */
export default function ScoreBar({ value, tone = "sub", label }: Props) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div className={`sbar ${tone}`} aria-label={label ? `${label} ${value === null ? "없음" : value.toFixed(1)}` : undefined}>
      <b className="mono">{value === null ? "—" : value.toFixed(1)}</b>
      <span className="sbar-track"><i style={{ width: `${pct}%` }} /></span>
    </div>
  );
}
