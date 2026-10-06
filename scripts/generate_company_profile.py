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


# ============================================================
# PeerProof imports
# ============================================================

from peerproof.rag.embedder import (
    BGEM3Embedder,
)

from peerproof.rag.retriever import (
    ProfileRetriever,
)

from peerproof.profile.llm_client import (
    ProfileLLMClient,
)

from peerproof.profile.profile_builder import (
    CompanyProfileBuilder,
)


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
# 실행 범위 선택
# ============================================================

def select_target_categories():
    """
    실행할 Profile category를 선택한다.

    반환값
    -------
    None
        전체 실행

    ["business"]
        Business만 실행

    ["growth"]
        Growth만 실행

    ["risk"]
        Risk만 실행
    """

    print()
    print("실행 범위를 선택하세요.")
    print()
    print("1. 전체")
    print("2. Business")
    print("3. Growth")
    print("4. Risk")

    mode = input(
        "\n선택 [1-4]: "
    ).strip()

    category_map = {
        "1": None,
        "2": ["business"],
        "3": ["growth"],
        "4": ["risk"],
    }

    if mode not in category_map:
        raise ValueError(
            "실행 범위는 1~4 중 하나를 입력해야 합니다."
        )

    return category_map[mode]


# ============================================================
# 선택 범위 출력용
# ============================================================

def get_target_label(
    target_categories,
) -> str:

    if target_categories is None:
        return "전체"

    if target_categories == ["business"]:
        return "Business"

    if target_categories == ["growth"]:
        return "Growth"

    if target_categories == ["risk"]:
        return "Risk"

    return ", ".join(
        target_categories
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
        "PEERPROOF / COMPANY PROFILE V2"
    )
    print(
        "=" * 70
    )

    # ========================================================
    # 1. 기업명 입력
    # ========================================================

    company_name = input(
        "\n기업명을 입력하세요: "
    ).strip()

    if not company_name:
        raise ValueError(
            "기업명이 비어 있습니다."
        )

    # ========================================================
    # 2. 실행 범위 선택
    # ========================================================

    target_categories = (
        select_target_categories()
    )

    target_label = (
        get_target_label(
            target_categories
        )
    )

    print()
    print(
        f"선택된 실행 범위: "
        f"{target_label}"
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

    # 기존 v1은 보존
    # v2 결과는 별도 파일에 저장
    output_path = (
        profile_dir
        / "company_profile_v2.json"
    )

    # ========================================================
    # 파일 존재 확인
    # ========================================================

    if not company_dir.exists():

        raise FileNotFoundError(
            "기업 processed 디렉토리가 없습니다.\n"
            f"{company_dir}"
        )

    if not chunks_path.exists():

        raise FileNotFoundError(
            "RAG chunk 파일이 없습니다.\n"
            f"{chunks_path}"
        )

    if not embeddings_path.exists():

        raise FileNotFoundError(
            "Embedding 파일이 없습니다.\n"
            f"{embeddings_path}"
        )

    # ========================================================
    # [1/5] Chunk
    # ========================================================

    print()
    print(
        "[1/5] RAG chunks 로드"
    )

    chunks = load_json(
        chunks_path
    )

    # rag_chunks.json 구조가
    # {"chunks": [...]} 인 경우에도 대응
    if isinstance(
        chunks,
        dict,
    ):
        chunks = chunks.get(
            "chunks",
            []
        )

    if not isinstance(
        chunks,
        list,
    ):
        raise ValueError(
            "rag_chunks.json 형식이 올바르지 않습니다."
        )

    if not chunks:
        raise ValueError(
            "RAG chunk가 없습니다."
        )

    print(
        f"chunks: {len(chunks)}"
    )

    # ========================================================
    # [2/5] Embeddings
    # ========================================================

    print()
    print(
        "[2/5] Embeddings 로드"
    )

    embeddings = np.load(
        embeddings_path
    )

    print(
        f"embedding shape: "
        f"{embeddings.shape}"
    )

    if len(chunks) != len(
        embeddings
    ):

        raise ValueError(
            "chunk 수와 embedding 수가 다릅니다.\n"
            f"chunks={len(chunks)}, "
            f"embeddings={len(embeddings)}"
        )

    # ========================================================
    # [3/5] BGE-M3
    # ========================================================

    print()
    print(
        "[3/5] BGE-M3 로드"
    )

    embedder = (
        BGEM3Embedder()
    )

    # ========================================================
    # [4/5] Retriever
    # ========================================================

    print()
    print(
        "[4/5] Retriever 생성"
    )

    retriever = (
        ProfileRetriever(
            chunks=chunks,
            embeddings=embeddings,
            embedder=embedder,
        )
    )

    # ========================================================
    # [5/5] Gemini / Profile Builder
    # ========================================================

    print()
    print(
        "[5/5] Profile v2 생성"
    )

    # --------------------------------------------------------
    # Gemini API 설정
    #
    # 현재 무료 tier rate limit이 자주 발생하므로
    # 호출 간격은 30초로 두고,
    # 한 field에서 최대 3번만 재시도한다.
    # --------------------------------------------------------

    llm_client = (
        ProfileLLMClient(
            request_interval=30.0,
            max_retries=3,
        )
    )

    # --------------------------------------------------------
    # Profile Builder
    #
    # Query 하나당 BGE-M3 Top 3
    # 여러 Query 결과를 합친 뒤
    # 최대 8개 Evidence를 Gemini에 전달
    # --------------------------------------------------------

    builder = (
        CompanyProfileBuilder(
            retriever=retriever,
            llm_client=llm_client,
            query_top_k=3,
            evidence_limit=8,
        )
    )

    # ========================================================
    # Profile 생성
    #
    # resume=True:
    #
    # 이미 status가
    # 확인 / 부분확인 / 미공시 / 해당없음
    # 인 field는 다시 호출하지 않는다.
    #
    # status=error인 field는
    # 다음 실행에서 다시 시도한다.
    # ========================================================

    profile = (
        builder.build_profile(
            company_name=company_name,
            output_path=output_path,
            resume=True,
            target_categories=target_categories,
        )
    )

    # ========================================================
    # 결과 출력
    # ========================================================

    print()
    print(
        "=" * 70
    )
    print(
        "COMPANY PROFILE V2 완료"
    )
    print(
        "=" * 70
    )

    print()
    print(
        f"기업: {company_name}"
    )

    print(
        f"실행 범위: {target_label}"
    )

    summary = profile.get(
        "summary",
        {},
    )

    if summary:

        print()
        print(
            f"전체 필드 : "
            f"{summary.get('total_fields')}"
        )

        print(
            f"신규 성공 : "
            f"{summary.get('success')}"
        )

        print(
            f"SKIP      : "
            f"{summary.get('skipped')}"
        )

        print(
            f"실패      : "
            f"{summary.get('failed')}"
        )

    print()
    print(
        "저장 위치:"
    )

    print(
        output_path
    )


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()