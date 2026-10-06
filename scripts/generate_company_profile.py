from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


# ============================================================
# 프로젝트 경로
# ============================================================

ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)

SRC_DIR = (
    ROOT_DIR
    / "src"
)

sys.path.insert(
    0,
    str(SRC_DIR),
)


from peerproof.profile.llm_client import (
    ProfileLLMClient,
)

from peerproof.profile.profile_builder import (
    CompanyProfileBuilder,
)

from peerproof.rag.embedder import (
    BGEM3Embedder,
)

from peerproof.rag.retriever import (
    ProfileRetriever,
)


PROCESSED_ROOT = (
    ROOT_DIR
    / "data"
    / "processed"
)


# ============================================================
# JSON
# ============================================================

def load_json(
    path: Path,
):

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


# ============================================================
# main
# ============================================================

def main():

    print()
    print(
        "=" * 70
    )

    print(
        "PEERPROOF / "
        "COMPANY PROFILE GENERATOR"
    )

    print(
        "=" * 70
    )

    company_name = input(
        "\n기업명을 입력하세요: "
    ).strip()

    if not company_name:

        print(
            "기업명이 비어 있습니다."
        )

        return

    company_dir = (
        PROCESSED_ROOT
        / company_name
    )

    rag_dir = (
        company_dir
        / "rag"
    )

    profile_dir = (
        company_dir
        / "profile"
    )

    chunks_path = (
        rag_dir
        / "rag_chunks.json"
    )

    embeddings_path = (
        rag_dir
        / "embeddings.npy"
    )

    output_path = (
        profile_dir
        / "company_profile.json"
    )

    # --------------------------------------------------------
    # 파일 확인
    # --------------------------------------------------------

    if not chunks_path.exists():

        print()
        print(
            "rag_chunks.json이 없습니다."
        )

        print(
            "먼저 실행하세요:"
        )

        print(
            "python "
            "scripts/build_rag_chunks.py"
        )

        return

    if not embeddings_path.exists():

        print()
        print(
            "embeddings.npy가 없습니다."
        )

        print(
            "먼저 실행하세요:"
        )

        print(
            "python "
            "scripts/test_profile_rag.py"
        )

        return

    # ========================================================
    # 1. RAG 데이터
    # ========================================================

    print()
    print(
        "[1/5] RAG 데이터 로드"
    )

    rag_data = load_json(
        chunks_path
    )

    chunks = rag_data.get(
        "chunks",
        [],
    )

    embeddings = np.load(
        embeddings_path
    )

    print(
        f"chunks     : "
        f"{len(chunks)}"
    )

    print(
        f"embeddings : "
        f"{embeddings.shape}"
    )

    if not chunks:

        raise ValueError(
            "RAG chunk가 없습니다."
        )

    if (
        len(chunks)
        != len(embeddings)
    ):

        raise ValueError(
            "chunk와 embedding 개수가 "
            "다릅니다.\n"
            f"chunks={len(chunks)}, "
            f"embeddings="
            f"{len(embeddings)}"
        )

    # ========================================================
    # 2. BGE-M3
    # ========================================================

    print()
    print(
        "[2/5] BGE-M3 로드"
    )

    embedder = (
        BGEM3Embedder(
            batch_size=4,
            max_length=1024,
            use_fp16=True,
        )
    )

    # ========================================================
    # 3. Retriever
    # ========================================================

    print()
    print(
        "[3/5] Retriever 생성"
    )

    retriever = (
        ProfileRetriever(
            chunks=chunks,
            embeddings=embeddings,
            embedder=embedder,
        )
    )

    # ========================================================
    # 4. LLM
    # ========================================================

    print()
    print(
        "[4/5] LLM Client 생성"
    )

    llm_client = (
        ProfileLLMClient(

            # Gemini 무료 티어
            # 5 RPM 대응
            request_interval=20.0,

            # 429 / 503 최대 5회
            max_retries=6,
        )
    )

    # ========================================================
    # 5. Profile
    # ========================================================

    print()
    print(
        "[5/5] Business Profile 생성"
    )

    builder = (
        CompanyProfileBuilder(
            retriever=retriever,
            llm_client=llm_client,
            top_k=5,
        )
    )

    profile = (
        builder.build_profile(
            company_name=(
                company_name
            ),

            output_path=(
                output_path
            ),

            # 기존 성공 필드는
            # 다시 호출하지 않음
            resume=True,
        )
    )

    print()
    print(
        "=" * 70
    )

    print(
        "COMPANY PROFILE 작업 완료"
    )

    print(
        "=" * 70
    )

    print()

    print(
        "저장 위치:"
    )

    print(
        output_path
    )

    print()

    print(
        "주의:"
    )

    print(
        "finance는 아직 "
        "생성 대상이 아닙니다."
    )


if __name__ == "__main__":
    main()