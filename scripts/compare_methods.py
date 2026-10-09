#!/usr/bin/env python
"""
유사도 방법별 Top-5 비교 + 융합 가중치 근거 (평가 전용)

세 가지를 한 표로 비교한다.
  1. 임베딩만      (10_bge_similarity.py 결과의 bge_similarity)
  2. 네트워크만    (11_language_network_similarity.py 결과의 지표 3개 평균, 지표별 단독도 함께)
  3. 융합          (임베딩 가중치를 여러 값으로 바꿔 가며; 화면용 build_serving_data.py와 같은 계산식)

정답지(증권신고서 비교기업)는 평가에만 쓴다. 가중치는 임의로 정하지 않고 이 비교 결과로 정한다.
단, 정답이 9곳 안팎이라 표본이 작으므로 "APR 기준으로 고른 값"이라고 밝혀야 한다.

사용 예
-------
    python scripts/compare_methods.py --answer-key docs/evaluation/apr_answer_key.json \\
        --bge data/similarity_input/bge_result.json --network data/similarity_input/network_result.json \\
        --candidates docs/evaluation/apr_candidates_v0.json --out data/evaluation/method_comparison.json

--candidates 는 선택이다. 각 항목의 role(예: A_최종비교기업, B_형식요건탈락 ...)로 그룹별 순위를 따로 보여 준다.
(role은 결과 해석에만 쓰고 점수 계산에는 쓰지 않는다.)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from peerproof.serving import builders  # noqa: E402

TOP_K = 5
DEFAULT_WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)


def _evaluate():
    spec = importlib.util.spec_from_file_location(
        "evaluate_candidates", Path(__file__).resolve().parent / "evaluate_candidates.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("evaluate_candidates", module)
    spec.loader.exec_module(module)
    return module


ev = _evaluate()


# ============================================================
# 순위 만들기
# ============================================================

def _entry(name: str, company_id: str) -> dict:
    """evaluate_candidates가 비교할 항목. corp_code는 8자리 숫자일 때만 믿는다(아니면 이름으로 비교)."""
    corp = company_id if re.fullmatch(r"\d{8}", str(company_id or "")) else ""
    return {"company": name, "corp_code": corp, "stock_code": ""}


def rank_rows(rows: list[dict]) -> list[dict]:
    """rows: {company_id, name, score}. 점수 내림차순, 같으면 이름순으로 고정해 결과가 매번 같게 한다."""
    ordered = sorted((r for r in rows if r.get("score") is not None), key=lambda r: (-r["score"], str(r["name"])))
    for rank, row in enumerate(ordered, 1):
        row["rank"] = rank
    return ordered


def method_rankings(bge: dict | None, network: dict | None, weights: tuple[float, ...]) -> dict[str, list[dict]]:
    rankings: dict[str, list[dict]] = {}

    if bge:
        rankings["임베딩만"] = rank_rows([
            {"company_id": str(i.get("corp_code") or ""), "name": i.get("company_name"), "score": i.get("bge_similarity")}
            for i in bge.get("results", [])])
    if network:
        rankings["네트워크만(3지표 평균)"] = rank_rows([
            {"company_id": str(i.get("corp_code") or ""), "name": i.get("company_name"), "score": builders.network_score(i)}
            for i in network.get("results", [])])
        for metric in builders.NETWORK_METRICS:
            rankings[f"네트워크 단독:{metric}"] = rank_rows([
                {"company_id": str(i.get("corp_code") or ""), "name": i.get("company_name"),
                 "score": i.get(metric) if isinstance(i.get(metric), (int, float)) else None}
                for i in network.get("results", [])])
    if bge and network:
        for w in weights:
            if w in (0.0, 1.0):
                continue  # 양 끝은 단독 방법과 같다
            fusion = {"embedding_weight": w, "network_weight": round(1 - w, 4), "method": "compare"}
            fused = builders.build_similar("target", bge, network, fusion)
            rankings[f"융합 임베딩{int(round(w * 100))}:네트워크{int(round((1 - w) * 100))}"] = [
                {"company_id": i["company_id"], "name": i["name"], "score": i["fused_score"], "rank": i["rank"]}
                for i in fused["items"]]
    return rankings


# ============================================================
# 평가
# ============================================================

def evaluate_method(peers: list[dict], ranked: list[dict]) -> dict:
    entries = [_entry(r["name"], r["company_id"]) for r in ranked]
    metrics = ev.ranking_metrics(peers, entries)
    top = []
    for row, entry in zip(ranked[:TOP_K], entries[:TOP_K]):
        top.append({"rank": row["rank"], "name": row["name"], "score": round(row["score"], 4),
                    "is_answer": any(ev.same_company(peer, entry) for peer in peers)})
    return {
        "top5": top,
        "answers_in_top5": sum(1 for t in top if t["is_answer"]),
        "precision@5": metrics["precision@5"],
        "hit@10": metrics["hit@10"],
        "mrr": metrics["mrr"],
        "peer_ranks": metrics["peer_ranks"],
        "ranked": metrics["ranked"],
    }


def score_scale(rankings: dict[str, list[dict]]) -> dict:
    """방법별 점수의 평균과 표준편차. 두 점수의 폭이 크게 다르면 단순 가중 평균이 한쪽에 치우친다."""
    out = {}
    for name in ("임베딩만", "네트워크만(3지표 평균)"):
        values = [r["score"] for r in rankings.get(name, [])]
        if len(values) >= 2:
            out[name] = {"mean": round(statistics.mean(values), 4), "std": round(statistics.pstdev(values), 4),
                         "min": round(min(values), 4), "max": round(max(values), 4)}
    return out


def select_weight(results: dict[str, dict]) -> dict:
    """융합 중 (상위 5개 안 정답 수, MRR, hit@10)이 가장 좋은 것. 동점이면 5:5에 가까운 쪽(임의 조정을 줄이려고)."""
    fused = {name: r for name, r in results.items() if name.startswith("융합")}
    if not fused:
        return {"note": "임베딩과 네트워크 결과가 둘 다 있어야 융합을 비교할 수 있습니다."}

    def weight_of(name: str) -> int:
        return int(re.search(r"임베딩(\d+)", name).group(1))

    def score(name: str):
        r = fused[name]
        return (r["answers_in_top5"], r["mrr"], r["hit@10"])

    best_score = max(score(n) for n in fused)
    ties = sorted((n for n in fused if score(n) == best_score), key=lambda n: (abs(weight_of(n) - 50), weight_of(n)))
    chosen = ties[0]
    singles = {n: results[n] for n in ("임베딩만", "네트워크만(3지표 평균)") if n in results}
    return {
        "criterion": "융합 후보 중 (Top-5 안 정답 수, MRR, hit@10) 순으로 비교, 동점이면 5:5에 가까운 값",
        "suggested": chosen,
        "suggested_embedding_weight": weight_of(chosen) / 100,
        "ties": ties,
        "best_single": max(singles, key=lambda n: (singles[n]["answers_in_top5"], singles[n]["mrr"])) if singles else None,
        "note": "정답이 소수라 표본이 작고 APR 한 건 기준입니다. 일반화된 가중치가 아니라 'APR에서 고른 값'으로 설명하세요.",
    }


def group_ranks(candidates: list[dict], rankings: dict[str, list[dict]]) -> dict:
    """후보 목록의 role별로 각 방법에서의 순위를 모아 준다. (해석용, 점수 계산에는 쓰지 않음)"""
    groups: dict[str, dict] = {}
    for cand in candidates:
        role = str(cand.get("role") or "미분류")
        target = {"company": cand["company"], "corp_code": cand.get("corp_code", ""), "stock_code": cand.get("stock_code", "")}
        ranks = {}
        for method, ranked in rankings.items():
            entries = [_entry(r["name"], r["company_id"]) for r in ranked]
            index = ev.find_in(entries, target)
            ranks[method] = index + 1 if index is not None else None
        groups.setdefault(role, {})[cand["company"]] = ranks
    return groups


def load_candidates_with_roles(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("candidates") if isinstance(data, dict) else data
    out = []
    for item in items or []:
        name = item.get("company_name") or item.get("corp_name") or item.get("name")
        if name:
            out.append({"company": str(name).strip(), "corp_code": str(item.get("corp_code") or ""),
                        "stock_code": str(item.get("stock_code") or ""), "role": item.get("role")})
    return out


# ============================================================
# 출력
# ============================================================

def print_table(results: dict[str, dict], n_peers: int) -> None:
    width = max(len(n) for n in results) + 2
    print(f"{'방법':<{width}}{'Top5 중 정답':>13}{'hit@10':>8}{'MRR':>8}   정답 순위")
    print("-" * (width + 60))
    for name, r in results.items():
        ranks = " ".join(f"{k}:{v}" for k, v in list(r["peer_ranks"].items())[:6])
        print(f"{name:<{width}}{r['answers_in_top5']:>8}/{TOP_K:<4}{r['hit@10']:>5}/{n_peers:<2}{r['mrr']:>8.3f}   {ranks}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="유사도 방법별 Top-5 비교와 융합 가중치 근거")
    parser.add_argument("--answer-key", required=True, type=Path)
    parser.add_argument("--bge", type=Path, default=None, help="10_bge_similarity.py 결과 JSON")
    parser.add_argument("--network", type=Path, default=None, help="11_language_network_similarity.py 결과 JSON")
    parser.add_argument("--candidates", type=Path, default=None, help="role이 적힌 후보 목록(선택)")
    parser.add_argument("--weights", type=float, nargs="+", default=list(DEFAULT_WEIGHTS), help="비교할 임베딩 가중치(0~1)")
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.bge and not args.network:
        raise SystemExit("--bge 또는 --network 중 하나는 필요합니다.")
    key = ev.load_answer_key(args.answer_key)
    peers = key["peers"]
    read = lambda p: json.loads(p.read_text(encoding="utf-8")) if p else None  # noqa: E731
    bge, network = read(args.bge), read(args.network)

    rankings = method_rankings(bge, network, tuple(args.weights))
    results = {name: evaluate_method(peers, ranked) for name, ranked in rankings.items()}
    print(f"대상 {key['target']} / 기준일 {key['as_of']} / 정답 {len(peers)}곳 / 후보 순위 "
          f"{max((r['ranked'] for r in results.values()), default=0)}곳\n")
    print_table(results, len(peers))

    selection = select_weight(results)
    print()
    if selection.get("suggested"):
        print(f"제안: {selection['suggested']} (동점 {len(selection['ties'])}개)  기준: {selection['criterion']}")
        print(f"      {selection['note']}")
        single = selection.get("best_single")
        if single and (results[single]["answers_in_top5"], results[single]["mrr"]) > (
                results[selection["suggested"]]["answers_in_top5"], results[selection["suggested"]]["mrr"]):
            print(f"참고: 단독 방법 '{single}'이 제안한 융합보다 Top-5 정답 수 또는 MRR이 더 좋습니다. 융합이 항상 낫지는 않습니다.")
    scale = score_scale(rankings)
    if len(scale) == 2:
        stds = [v["std"] for v in scale.values()]
        if min(stds) > 0 and max(stds) / min(stds) > 2:
            print(f"주의: 두 점수의 퍼짐이 2배 이상 다릅니다(표준편차 {stds}). 단순 가중 평균은 퍼짐이 큰 쪽에 치우칩니다.")

    report: dict[str, Any] = {"target": key["target"], "analysis_as_of": key["as_of"], "answer_peers": len(peers),
                              "methods": results, "selection": selection, "score_scale": scale}
    if args.candidates:
        groups = group_ranks(load_candidates_with_roles(args.candidates), rankings)
        report["groups"] = groups
        print("\n[그룹별 순위] (임베딩만 / 네트워크만 / 제안 융합)")
        pick = selection.get("suggested")
        for role, companies in groups.items():
            print(f"  {role}")
            for company, ranks in companies.items():
                print(f"    {company:<14} 임베딩 {ranks.get('임베딩만')}  네트워크 {ranks.get('네트워크만(3지표 평균)')}"
                      + (f"  융합 {ranks.get(pick)}" if pick else ""))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n저장: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
