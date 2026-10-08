import { useMemo, useState } from "react";
import { isShared, sharedLabels, topEdges, weightedDegree } from "../lib/network";
import type { CompanyNetwork } from "../types/domain";
import NetworkGraph from "./NetworkGraph";

type Tab = "keyword" | "edge" | "centrality";
const TABS: { key: Tab; label: string }[] = [
  { key: "keyword", label: "Keyword" },
  { key: "edge", label: "Edge" },
  { key: "centrality", label: "Centrality" },
];

interface Props {
  target: CompanyNetwork | null;
  peer: CompanyNetwork;
  targetName: string;
  peerName: string;
}

export default function NetworkPanel({ target, peer, targetName, peerName }: Props) {
  const [side, setSide] = useState<"peer" | "target">("peer");
  const [tab, setTab] = useState<Tab>("keyword");
  const [sel, setSel] = useState<string | null>(null);
  const net = side === "target" && target ? target : peer;
  const shared = useMemo(() => sharedLabels(target, peer), [target, peer]);
  const deg = useMemo(() => weightedDegree(net), [net]);
  const byCentrality = useMemo(() => [...net.nodes].sort((a, b) => b.centrality - a.centrality), [net]);
  const edges = useMemo(() => topEdges(net, 8), [net]);
  const selected = net.nodes.find((n) => n.id === sel) ?? null;
  const maxW = Math.max(...edges.map((e) => e.weight), 0.0001);

  return (
    <div className="netpanel">
      <div className="netbar">
        <div className="segmini" role="group" aria-label="네트워크 대상">
          <button className={side === "peer" ? "on" : ""} onClick={() => { setSide("peer"); setSel(null); }}>{peerName}</button>
          <button className={side === "target" ? "on" : ""} disabled={!target} onClick={() => { setSide("target"); setSel(null); }}>{targetName}</button>
        </div>
        <span className="small muted">
          {target ? <><i className="legend-dot shared" /> 공통 키워드 {shared.size}개 · 노드 크기 = 중심성 · 선 굵기 = 가중치</> : "대상기업 네트워크를 불러오지 못해 공통 키워드 표시를 생략합니다."}
        </span>
      </div>
      <div className="netgrid">
        <NetworkGraph network={net} shared={shared} selectedId={sel} onSelect={setSel} />
        <div className="netside">
          <div className="tabs mini" role="tablist">
            {TABS.map((t) => (
              <button key={t.key} role="tab" aria-selected={tab === t.key} className={`tab ${tab === t.key ? "on" : ""}`} onClick={() => setTab(t.key)}>{t.label}</button>
            ))}
          </div>
          {selected && (
            <div className="nodeinfo">
              <b>{selected.label}</b> · 중심성 <span className="mono">{selected.centrality.toFixed(2)}</span> · 연결 강도 <span className="mono">{(deg.get(selected.id) ?? 0).toFixed(2)}</span>
              {isShared(selected.label, shared) && <span className="badge">공통</span>}
            </div>
          )}
          <ul className="netlist">
            {tab === "keyword" && byCentrality.map((n) => (
              <li key={n.id} className={sel === n.id ? "on" : ""} onClick={() => setSel(n.id)}>
                <span>{n.label}</span>
                <span className={`tag ${isShared(n.label, shared) ? "shared" : ""}`}>{isShared(n.label, shared) ? "공통" : "고유"}</span>
              </li>
            ))}
            {tab === "edge" && edges.map((e, i) => (
              <li key={i}>
                <span>{e.a} — {e.b}</span>
                <span className="mini-bar"><i style={{ width: `${(e.weight / maxW) * 100}%` }} /></span>
                <span className="mono">{e.weight.toFixed(2)}</span>
              </li>
            ))}
            {tab === "centrality" && byCentrality.map((n) => (
              <li key={n.id} className={sel === n.id ? "on" : ""} onClick={() => setSel(n.id)}>
                <span>{n.label}</span>
                <span className="mini-bar"><i style={{ width: `${n.centrality * 100}%` }} /></span>
                <span className="mono">{n.centrality.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
