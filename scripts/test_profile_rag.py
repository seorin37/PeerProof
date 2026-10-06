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


from peerproof.rag import (
    BGEM3Embedder,
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
# 검색 결과 출력
# ============================================================

def print_results(
    query: str,
    results: list,
):

    print()
    print("=" * 70)

    print(
        f"QUERY: {query}"
    )

    print("=" * 70)

    if not results:

        print(
            "검색 결과가 없습니다."
        )

        return

    for result in results:

        print()

        print(
            f"[TOP {result['rank']}]"
        )

        print(
            f"score       : "
            f"{result['score']:.4f}"
        )

        print(
            f"chunk_id    : "
            f"{result['chunk_id']}"
        )

        print(
            f"category    : "
            f"{result['category']}"
        )

        print(
            f"report      : "
            f"{result['report_type']}"
        )

        print(
            f"source      : "
            f"{result['source_type']}"
        )

        metadata = result.get(
            "metadata",
            {},
        )

        if metadata.get(
            "table_id"
        ):

            print(
                f"table_id    : "
                f"{metadata['table_id']}"
            )

        if (
            metadata.get(
                "block_index"
            )
            is not None
        ):

            print(
                f"block_index : "
                f"{metadata['block_index']}"
            )

        print()

        print(
            "CONTENT"
        )

        print("-" * 70)

        content = result.get(
            "content",
            "",
        )

        # 너무 길면 터미널에서는 일부만 표시
        preview_length = 1500

        if len(
            content
        ) > preview_length:

            content = (
                content[
                    :preview_length
                ]
                + "\n...[생략]"
            )

        print(
            content
        )

        print("-" * 70)


# ============================================================
# main
# ============================================================

def main():

    print()
    print("=" * 70)

    print(
        "PEERPROOF / "
        "BGE-M3 PROFILE RAG TEST"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # 기업
    # --------------------------------------------------------

    company_name = input(
        "\n기업명을 입력하세요: "
    ).strip()

    company_dir = (
        PROCESSED_ROOT
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

    # --------------------------------------------------------
    # Chunk 로드
    # --------------------------------------------------------

    print()
    print(
        "[1/4] RAG chunk 로드"
    )

    rag_data = load_json(
        chunks_path
    )

    chunks = rag_data.get(
        "chunks",
        [],
    )

    print(
        f"chunk 수: {len(chunks)}"
    )

    if not chunks:

        print(
            "검색 가능한 chunk가 없습니다."
        )

        return

    # --------------------------------------------------------
    # BGE-M3
    # --------------------------------------------------------

    print()
    print(
        "[2/4] BGE-M3 로드"
    )

    embedder = BGEM3Embedder(
        model_name="BAAI/bge-m3",

        # RTX 3060 Laptop 6GB 기준
        batch_size=4,

        # 현재 profile evidence chunk에는 충분
        max_length=1024,

        use_fp16=True,
    )

    # --------------------------------------------------------
    # Chunk embedding
    # --------------------------------------------------------

    if embeddings_path.exists():

        print()
        print(
            "[3/4] 기존 embedding 로드"
        )

        embeddings = np.load(
            embeddings_path
        )

        # chunk가 바뀌었다면 재생성
        if len(
            embeddings
        ) != len(
            chunks
        ):

            print(
                "chunk 개수가 변경되어 "
                "embedding을 다시 생성합니다."
            )

            texts = [
                chunk[
                    "content"
                ]
                for chunk in chunks
            ]

            embeddings = (
                embedder
                .encode_documents(
                    texts
                )
            )

            np.save(
                embeddings_path,
                embeddings,
            )

    else:

        print()
        print(
            "[3/4] 66개 chunk embedding"
        )

        texts = [
            chunk[
                "content"
            ]
            for chunk in chunks
        ]

        embeddings = (
            embedder
            .encode_documents(
                texts
            )
        )

        np.save(
            embeddings_path,
            embeddings,
        )

        print(
            "embedding 저장:"
        )

        print(
            embeddings_path
        )

    print(
        f"embedding shape: "
        f"{embeddings.shape}"
    )

    # --------------------------------------------------------
    # Retriever
    # --------------------------------------------------------

    retriever = (
        ProfileRetriever(
            chunks=chunks,
            embeddings=embeddings,
            embedder=embedder,
        )
    )

    print()
    print(
        "[4/4] RAG 검색 준비 완료"
    )

    # ========================================================
    # 검색 반복
    # ========================================================

    while True:

        print()

        query = input(
            "질문을 입력하세요 "
            "(종료: q): "
        ).strip()

        if query.lower() in {
            "q",
            "quit",
            "exit",
        }:

            print(
                "검색을 종료합니다."
            )

            break

        if not query:

            continue

        # ----------------------------------------------------
        # category 선택
        # ----------------------------------------------------

        print()
        print(
            "검색 영역을 선택하세요."
        )

        print(
            "1. business"
        )

        print(
            "2. growth"
        )

        print(
            "3. risk"
        )

        print(
            "4. finance"
        )

        print(
            "5. 전체"
        )

        category_input = input(
            "선택 [1-5]: "
        ).strip()

        category_map = {
            "1": "business",
            "2": "growth",
            "3": "risk",
            "4": "finance",
            "5": None,
        }

        category = (
            category_map.get(
                category_input,
                None,
            )
        )

        # ----------------------------------------------------
        # 검색
        # ----------------------------------------------------

        results = (
            retriever.search(
                query=query,
                top_k=5,
                category=category,
            )
        )

        print_results(
            query=query,
            results=results,
        )


if __name__ == "__main__":
    main()