import type { CompanyNetwork } from "../types/domain";

export interface Point { x: number; y: number; angle: number }

/** 중심성이 높은 노드부터 타원 위에 균등 배치 (결정적 레이아웃) */
export function circularLayout(net: CompanyNetwork, w: number, h: number, pad: number): Map<string, Point> {
  const sorted = [...net.nodes].sort((a, b) => b.centrality - a.centrality || a.label.localeCompare(b.label));
  const n = Math.max(sorted.length, 1);
  const rx = w / 2 - pad;
  const ry = h / 2 - pad;
  const out = new Map<string, Point>();
  sorted.forEach((node, i) => {
    const angle = -Math.PI / 2 + (i / n) * Math.PI * 2;
    out.set(node.id, { x: w / 2 + rx * Math.cos(angle), y: h / 2 + ry * Math.sin(angle), angle });
  });
  return out;
}

const norm = (s: string) => s.trim().toLowerCase();

/** 두 네트워크에서 같은 표기(대소문자·공백 무시)로 나타난 키워드 */
export function sharedLabels(a: CompanyNetwork | null | undefined, b: CompanyNetwork | null | undefined): Set<string> {
  if (!a || !b) return new Set();
  const left = new Set(a.nodes.map((n) => norm(n.label)));
  return new Set(b.nodes.map((n) => norm(n.label)).filter((l) => left.has(l)));
}
export const isShared = (label: string, shared: Set<string>) => shared.has(norm(label));

/** 가중 연결 정도(weighted degree) */
export function weightedDegree(net: CompanyNetwork): Map<string, number> {
  const d = new Map<string, number>(net.nodes.map((n) => [n.id, 0]));
  net.edges.forEach((e) => {
    d.set(e.source, (d.get(e.source) ?? 0) + e.weight);
    d.set(e.target, (d.get(e.target) ?? 0) + e.weight);
  });
  return d;
}

export function topEdges(net: CompanyNetwork, limit: number) {
  const label = new Map(net.nodes.map((n) => [n.id, n.label]));
  return [...net.edges]
    .sort((x, y) => y.weight - x.weight)
    .slice(0, limit)
    .map((e) => ({ a: label.get(e.source) ?? e.source, b: label.get(e.target) ?? e.target, weight: e.weight }));
}

export function deriveStats(values: number[]) {
  if (values.length === 0) return null;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return { min: s[0], max: s[s.length - 1], median: s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2 };
}

/** 선형 보간 사분위수 (값이 1개면 q1=q3=그 값) */
export function quartiles(values: number[]) {
  if (values.length === 0) return null;
  const s = [...values].sort((a, b) => a - b);
  const at = (p: number) => { const i = (s.length - 1) * p; const lo = Math.floor(i); const hi = Math.ceil(i); return s[lo] + (s[hi] - s[lo]) * (i - lo); };
  return { q1: at(0.25), q3: at(0.75) };
}
