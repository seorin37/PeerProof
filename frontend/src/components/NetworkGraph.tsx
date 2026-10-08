import { useMemo, useState } from "react";
import { circularLayout, isShared } from "../lib/network";
import type { CompanyNetwork } from "../types/domain";

const W = 640;
const H = 400;

interface Props {
  network: CompanyNetwork;
  shared: Set<string>;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

/** 키워드(노드 크기=중심성) · 간선(굵기=가중치) SVG 그래프. 공통 키워드는 파랑. */
export default function NetworkGraph({ network, shared, selectedId, onSelect }: Props) {
  const [hover, setHover] = useState<string | null>(null);
  const pos = useMemo(() => circularLayout(network, W, H, 70), [network]);
  const maxC = Math.max(...network.nodes.map((n) => n.centrality), 0.0001);
  const maxW = Math.max(...network.edges.map((e) => e.weight), 0.0001);
  const focus = hover ?? selectedId;
  const linked = new Set<string>();
  if (focus) network.edges.forEach((e) => { if (e.source === focus) linked.add(e.target); if (e.target === focus) linked.add(e.source); });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="netgraph" role="img" aria-label="키워드 네트워크">
      <g>
        {network.edges.map((e, i) => {
          const a = pos.get(e.source);
          const b = pos.get(e.target);
          if (!a || !b) return null;
          const active = focus ? e.source === focus || e.target === focus : true;
          return (
            <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#8aa3d6"
              strokeWidth={0.6 + (e.weight / maxW) * 3.4} opacity={active ? 0.65 : 0.1} />
          );
        })}
      </g>
      <g>
        {network.nodes.map((n) => {
          const p = pos.get(n.id);
          if (!p) return null;
          const r = 5 + (n.centrality / maxC) * 14;
          const share = isShared(n.label, shared);
          const dim = focus ? !(n.id === focus || linked.has(n.id)) : false;
          const right = Math.cos(p.angle) >= 0;
          const dy = Math.sin(p.angle) * (r + 6);
          return (
            <g key={n.id} tabIndex={0} role="button" aria-label={`${n.label} 중심성 ${n.centrality.toFixed(2)}`}
              className="netnode" opacity={dim ? 0.25 : 1}
              onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(n.id)} onBlur={() => setHover(null)}
              onClick={() => onSelect(selectedId === n.id ? null : n.id)}
              onKeyDown={(ev) => (ev.key === "Enter" || ev.key === " ") && onSelect(selectedId === n.id ? null : n.id)}>
              <circle cx={p.x} cy={p.y} r={r} fill={share ? "#2762e7" : "#111c2e"} stroke={selectedId === n.id ? "#c89a60" : "#fff"} strokeWidth={selectedId === n.id ? 3 : 1.5} />
              <text x={p.x + (right ? r + 6 : -(r + 6))} y={p.y + dy / 3 + 4} textAnchor={right ? "start" : "end"} fontSize="12" fill="#152032">
                {n.label}
              </text>
            </g>
          );
        })}
      </g>
    </svg>
  );
}
