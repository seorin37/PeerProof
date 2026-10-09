"""
키워드 네트워크(networkx 그래프) -> 프론트 network.json 형식 변환.

스크립트 11(언어네트워크 유사도)이 만든 그래프를 화면용 {company_id, nodes, edges} 로 바꾼다.
networkx 객체만 받으므로 keybert/torch 없이도 테스트할 수 있다.

  nodes[].centrality  가중 연결 중심성을 가장 큰 값 1.0 으로 나눈 0~1 값
  edges[].weight      같은 핵심 문장에서 함께 나온 횟수 (원래 값 그대로)
"""

from __future__ import annotations

DEFAULT_MAX_NODES = 30


def graph_to_network(company_id: str, graph, max_nodes: int = DEFAULT_MAX_NODES, groups: dict | None = None) -> dict:
    """중심성이 큰 상위 max_nodes 개 키워드와, 그들 사이의 간선만 남긴다."""
    degree = {n: float(graph.degree(n, weight="weight")) for n in graph.nodes()}
    top = sorted(degree, key=lambda n: (-degree[n], str(n)))[:max_nodes]
    peak = max((degree[n] for n in top), default=0.0)
    keep = set(top)
    nodes = []
    for n in top:
        node = {"id": str(n), "label": str(n), "centrality": round(degree[n] / peak, 4) if peak > 0 else 0.0}
        if groups and groups.get(n):
            node["group"] = str(groups[n])
        nodes.append(node)
    edges = []
    for u, v, data in graph.edges(data=True):
        if u in keep and v in keep and u != v:
            edges.append({"source": str(u), "target": str(v), "weight": float((data or {}).get("weight", 1.0))})
    edges.sort(key=lambda e: (-e["weight"], e["source"], e["target"]))
    return {"company_id": str(company_id), "nodes": nodes, "edges": edges}
