from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


# ============================================================
# Project Path
# ============================================================

ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)

SRC_DIR = ROOT_DIR / "src"

sys.path.insert(
    0,
    str(SRC_DIR),
)


# ============================================================
# Imports
# ============================================================

from peerproof.rag.embedder import (
    BGEM3Embedder,
)

from peerproof.rag.retriever import (
    ProfileRetriever,
)

from peerproof.profile.profile_builder import (
    CompanyProfileBuilder,
)

from peerproof.profile.schema import (
    PROFILE_SCHEMA,
)


# ============================================================
# Dummy LLM
#
# 이번 테스트에서는 Gemini를 호출하지 않는다.
# ============================================================

class DummyLLMClient:
    pass


# ============================================================
# JSON Loader
# ============================================================

def load_json(
    path: Path,
):

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


# ============================================================
# main
# ============================================================

def main():

    print()
    print("=" * 80)
    print("PEERPROOF / RISK RETRIEVAL TEST")
    print("=" * 80)

    company_name = input(
        "\n기업명을 입력하세요: "
    ).strip()

    if not company_name:
        raise ValueError(
            "기업명이 비어 있습니다."
        )

    # ========================================================
    # Path
    # ========================================================

    company_dir = (
        ROOT_DIR
        / "data"
        / "processed"
        / company_name
    )

    rag_dir = (
        company_dir
        / "rag"
    )

    chunks_path = (
        rag_dir
        / "rag_chunks.json"
    )

    embeddings_path = (
        rag_dir
        / "embeddings.npy"
    )

    # ========================================================
    # 파일 확인
    # ========================================================

    if not chunks_path.exists():
        raise FileNotFoundError(
            f"rag_chunks.json이 없습니다:\n"
            f"{chunks_path}"
        )

    if not embeddings_path.exists():
        raise FileNotFoundError(
            f"embeddings.npy가 없습니다:\n"
            f"{embeddings_path}"
        )

    # ========================================================
    # 1. Chunk
    # ========================================================

    print()
    print("[1/4] Chunk 로드")

    chunks = load_json(
        chunks_path
    )

    if isinstance(
        chunks,
        dict,
    ):
        chunks = chunks.get(
            "chunks",
            []
        )

    print(
        f"chunks: {len(chunks)}"
    )

    # ========================================================
    # 2. Embeddings
    # ========================================================

    print()
    print("[2/4] Embedding 로드")

    embeddings = np.load(
        embeddings_path
    )

    print(
        f"shape: {embeddings.shape}"
    )

    if len(chunks) != len(
        embeddings
    ):
        raise ValueError(
            "chunk 수와 embedding 수가 다릅니다."
        )

    # ========================================================
    # 3. BGE-M3
    # ========================================================

    print()
    print("[3/4] BGE-M3 로드")

    embedder = (
        BGEM3Embedder()
    )

    # ========================================================
    # 4. Retriever
    # ========================================================

    print()
    print("[4/4] Retriever 생성")

    retriever = (
        ProfileRetriever(
            chunks=chunks,
            embeddings=embeddings,
            embedder=embedder,
        )
    )

    # ========================================================
    # Builder
    #
    # 여기서 builder를 반드시 먼저 생성해야 한다.
    # ========================================================

    builder = (
        CompanyProfileBuilder(
            retriever=retriever,
            llm_client=DummyLLMClient(),
            query_top_k=3,
            evidence_limit=8,
        )
    )

    # ========================================================
    # Risk 검색 테스트
    # ========================================================

    risk_fields = (
        PROFILE_SCHEMA[
            "risk"
        ]
    )

    for field_name, field_config in (
        risk_fields.items()
    ):

        print()
        print("=" * 80)

        print(
            f"[{field_config['code']}] "
            f"{field_config['label']}"
        )

        print("=" * 80)

        evidences = (
            builder.retrieve_field_evidence(
                category="risk",
                field_config=field_config,
            )
        )

        print(
            f"최종 Evidence: "
            f"{len(evidences)}개"
        )

        # ====================================================
        # 출력은 Top 3만
        # ====================================================

        top_evidences = (
            evidences[:3]
        )

        for index, evidence in enumerate(
            top_evidences,
            start=1,
        ):

            fused_score = (
                evidence.get(
                    "fused_score",
                    0.0,
                )
            )

            print()

            print(
                f"E{index} | "
                f"chunk="
                f"{evidence.get('chunk_id')} | "
                f"score="
                f"{fused_score:.4f}"
            )

            print(
                "categories:",
                evidence.get(
                    "matched_categories"
                ),
            )

            content = (
                evidence.get(
                    "content",
                    ""
                )
            )

            # 줄바꿈 제거
            content = " ".join(
                content.split()
            )

            # 너무 길지 않게 250자
            print(
                content[:250]
            )


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()