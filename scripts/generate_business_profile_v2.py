#!/usr/bin/env python
"""
PeerProof Business Profile v2 실행 스크립트

예시
----
export PYTHONPATH=src

python scripts/generate_business_profile_v2.py \
  --company "에이피알" \
  --corp-code "01190568" \
  --analysis-as-of "2023-12-21"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from peerproof.profile.profile_builder_business_v2 import (
    BusinessProfileBuilderV2,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "기존 Profile 결과를 건드리지 않고 "
            "Business Profile v2를 별도 생성합니다."
        )
    )

    parser.add_argument(
        "--company",
        default="에이피알",
        help="회사명 (기본값: 에이피알)",
    )

    parser.add_argument(
        "--corp-code",
        default="01190568",
        help="DART corp_code (기본값: 01190568)",
    )

    parser.add_argument(
        "--analysis-as-of",
        default="2023-12-21",
        help="분석 기준일 YYYY-MM-DD",
    )

    parser.add_argument(
        "--profile-dir",
        default=None,
        help=(
            "기존 RAG 파일이 있는 profile 폴더. "
            "미지정 시 data/processed/<회사명>/profile"
        ),
    )

    parser.add_argument(
        "--chunks",
        default=None,
        help="rag_chunks.json 직접 지정",
    )

    parser.add_argument(
        "--embeddings",
        default=None,
        help="embeddings.npy 직접 지정",
    )

    parser.add_argument(
        "--output",
        default=None,
        help="출력 JSON 직접 지정",
    )

    parser.add_argument(
        "--feature",
        default=None,
        choices=[
            "products_services",
            "revenue_model",
            "customer_type",
            "distribution_channel",
            "product_revenue_share",
        ],
        help="특정 Business feature 하나만 실행",
    )

    parser.add_argument(
        "--query-top-k",
        type=int,
        default=3,
        help="각 query별 검색 개수 (기본값: 3)",
    )

    parser.add_argument(
        "--evidence-limit",
        type=int,
        default=8,
        help="LLM에 전달할 최대 evidence 수 (기본값: 8)",
    )

    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="기존 Business v2 결과를 무시하고 처음부터 재생성",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    profile_dir = (
        Path(args.profile_dir)
        if args.profile_dir
        else Path("data/processed") / args.company / "profile"
    )

    chunks_path = (
        Path(args.chunks)
        if args.chunks
        else profile_dir / "rag_chunks.json"
    )

    embeddings_path = (
        Path(args.embeddings)
        if args.embeddings
        else profile_dir / "embeddings.npy"
    )

    output_path = (
        Path(args.output)
        if args.output
        else (
            profile_dir
            / "business_v2"
            / "business_profile_v2.json"
        )
    )

    print("=" * 80)
    print("PeerProof - Business Profile v2")
    print("=" * 80)
    print(f"Company       : {args.company}")
    print(f"Corp Code     : {args.corp_code}")
    print(f"Analysis AsOf : {args.analysis_as_of}")
    print(f"Chunks        : {chunks_path}")
    print(f"Embeddings    : {embeddings_path}")
    print(f"Output        : {output_path}")
    print(f"Feature       : {args.feature or 'ALL'}")
    print(f"Resume        : {not args.no_resume}")
    print("=" * 80)

    builder = BusinessProfileBuilderV2(
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        output_path=output_path,
        company_name=args.company,
        corp_code=args.corp_code,
        analysis_as_of=args.analysis_as_of,
        query_top_k=args.query_top_k,
        evidence_limit=args.evidence_limit,
        resume=not args.no_resume,
    )

    result = builder.build(
        only_feature=args.feature,
    )

    print()
    print("=" * 80)
    print("완료")
    print("=" * 80)
    print(
        "Business features:",
        len(result.get("business", {})),
    )
    print("Saved:", output_path)


if __name__ == "__main__":
    main()
