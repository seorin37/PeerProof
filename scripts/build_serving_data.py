#!/usr/bin/env python
"""
프론트엔드/API가 읽을 JSON 묶음 만들기 (data/serving/)

  data/serving/companies.json               회사 목록(대상 + 쓸 수 있는 후보)
  data/serving/<company_id>/profile.json    회사별 비즈니스 프로필(근거 포함)
  data/serving/<target_id>/similar.json     유사도 순위 (--bge / --network 를 주면)
  data/serving/<target_id>/network.json     (아직 빈 그래프)
  data/serving/<target_id>/metrics.json     재무 지표 비교 (DART 공시만 사용)

유사도 결합 가중치는 임의로 정하지 않는다. 방식별 Top-5를 비교해 정한 값을
--fusion-weights 임베딩 네트워크 로 주거나, 화면 확인용으로만 --provisional-equal-weights 를 쓴다
(이 경우 응답의 fusion.method 에 provisional_equal_weights 로 표시된다).

사용 예
-------
    python scripts/build_serving_data.py --target 에이피알 --candidates <후보목록.json> --as-of 20231221
    python scripts/build_serving_data.py --target 에이피알 --candidates <후보목록.json> --as-of 20231221 \\
        --bge data/similarity_input/bge_result.json --network data/similarity_input/network_result.json \\
        --provisional-equal-weights
    API 실행:  PYTHONPATH=src uvicorn peerproof.api.app:app --port 8000
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from peerproof.serving import builders  # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path | None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="프론트엔드용 JSON 만들기")
    parser.add_argument("--target", required=True)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--bge", type=Path, default=None, help="10_bge_similarity.py 결과 JSON")
    parser.add_argument("--network", type=Path, default=None, help="11_language_network_similarity.py 결과 JSON")
    parser.add_argument("--network-graphs", type=Path, default=None,
                        help="11 번 스크립트의 --graphs-dir 로 저장한 <corp_code>.json 폴더 (화면의 언어 네트워크)")
    weights = parser.add_mutually_exclusive_group()
    weights.add_argument("--fusion-weights", nargs=2, type=float, metavar=("EMBEDDING", "NETWORK"))
    weights.add_argument("--provisional-equal-weights", action="store_true")
    parser.add_argument("--serving-dir", type=Path, default=None, help="기본: data/serving")
    parser.add_argument("--root", type=Path, default=ROOT_DIR, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    batch, export = _load("build_profiles_batch"), _load("export_similarity_inputs")
    cutoff = batch.as_of_to_cutoff(args.as_of)
    out = (args.serving_dir or root / "data" / "serving").resolve()

    names = [args.target] + [c["company"] for c in batch.load_companies(args.candidates) if c["company"] != args.target]
    summaries, skipped = [], []
    unified_by_id: dict[str, dict] = {}
    target_id = None
    for name in names:
        unified = batch.load_unified(root, name)
        reason = export.usable(unified, cutoff)
        if reason:
            if name == args.target:
                print(f"대상기업 {name}: 사용할 수 없습니다 ({reason})")
                return 1
            skipped.append((name, reason))
            continue
        chunks = read_json(root / "data" / "processed" / name / "rag" / "rag_chunks.json") if (
            root / "data" / "processed" / name / "rag" / "rag_chunks.json").exists() else []
        company_id = builders.company_id_of(unified)
        if not company_id:
            skipped.append((name, "corp_code 없음"))
            continue
        write_json(out / company_id / "profile.json", builders.build_profile(unified, chunks))
        summaries.append(builders.build_company_summary(unified))
        unified_by_id[company_id] = unified
        if name == args.target:
            target_id = company_id

    write_json(out / "companies.json", summaries)
    print(f"프로필 {len(summaries)}곳 저장 -> {out}")
    for name, reason in skipped[:20]:
        print(f"  제외 {name}: {reason}")

    if args.bge or args.network:
        if args.fusion_weights:
            fusion = {"embedding_weight": args.fusion_weights[0], "network_weight": args.fusion_weights[1], "method": "late_fusion"}
        elif args.provisional_equal_weights:
            fusion = {"embedding_weight": 0.5, "network_weight": 0.5, "method": "provisional_equal_weights"}
        else:
            print("유사도 결과를 쓰려면 --fusion-weights 또는 --provisional-equal-weights 가 필요합니다.")
            return 1
        similar = builders.build_similar(target_id, read_json(args.bge), read_json(args.network), fusion)
        write_json(out / target_id / "similar.json", similar)
        write_json(out / target_id / "network.json", builders.build_network_stub(target_id))
        if args.network_graphs:
            saved = 0
            for company_id in [target_id] + [i["company_id"] for i in similar.get("items", [])]:
                src = args.network_graphs / f"{company_id}.json"
                if company_id in unified_by_id and src.exists():
                    write_json(out / company_id / "network.json", read_json(src))
                    saved += 1
            print(f"네트워크 그래프 {saved}곳 저장")
        write_json(out / target_id / "metrics.json", builders.build_metrics(target_id, unified_by_id, similar))
        print(f"유사도 순위 {len(similar['items'])}곳 저장 (가중치: {fusion['method']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
