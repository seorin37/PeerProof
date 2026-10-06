from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


# ============================================================
# Project path
# ============================================================

ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)


# ============================================================
# 확인할 Risk 항목
# ============================================================

TARGET_FIELDS = {

    # --------------------------------------------------------
    # R2 고객 집중도
    # --------------------------------------------------------

    "R2_customer_concentration": {

        "label": "고객 집중도",

        "keywords": [
            "주요 고객",
            "주요고객",
            "고객사",
            "주요 매출처",
            "주요매출처",
            "매출처",
            "거래처",
            "10%",
            "10％",
            "의존도",
        ],
    },

    # --------------------------------------------------------
    # R5 규제
    # --------------------------------------------------------

    "R5_regulatory_risk": {

        "label": "규제",

        "keywords": [
            "규제",
            "법률",
            "법령",
            "인허가",
            "허가",
            "승인",
            "인증",
            "의료기기법",
            "화장품법",
            "표시광고",
            "식품의약품안전처",
            "식약처",
        ],
    },

    # --------------------------------------------------------
    # R6-2 경쟁사
    # --------------------------------------------------------

    "R6_2_competitors": {

        "label": "경쟁사",

        "keywords": [
            "경쟁사",
            "경쟁업체",
            "경쟁기업",
            "동종업계",
            "시장점유율",
            "점유율",
            "경쟁 현황",
            "경쟁현황",
        ],
    },
}


# ============================================================
# JSON
# ============================================================

def load_json(
    path: Path,
) -> Any:

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


# ============================================================
# 텍스트 정리
# ============================================================

def normalize_text(
    text: str,
) -> str:

    return " ".join(
        str(text).split()
    )


# ============================================================
# Keyword 검색
# ============================================================

def find_keywords(
    text: str,
    keywords: list[str],
) -> list[str]:

    text_lower = (
        text.lower()
    )

    matched = []

    for keyword in keywords:

        if (
            keyword.lower()
            in text_lower
        ):

            matched.append(
                keyword
            )

    return matched


# ============================================================
# Chunk text 추출
# ============================================================

def get_chunk_text(
    chunk: dict[str, Any],
) -> str:

    return str(
        chunk.get("content")
        or chunk.get("text")
        or chunk.get("chunk")
        or ""
    )


# ============================================================
# Chunk ID
# ============================================================

def get_chunk_id(
    chunk: dict[str, Any],
    index: int,
) -> str:

    return str(
        chunk.get("chunk_id")
        or chunk.get("id")
        or f"chunk_{index}"
    )


# ============================================================
# RAG Chunk 검사
# ============================================================

def search_rag_chunks(
    chunks: list[dict[str, Any]],
    keywords: list[str],
    limit: int = 5,
) -> list[dict[str, Any]]:

    results = []

    for index, chunk in enumerate(
        chunks
    ):

        text = get_chunk_text(
            chunk
        )

        matched = find_keywords(
            text,
            keywords,
        )

        if not matched:
            continue

        results.append(
            {
                "chunk_id": get_chunk_id(
                    chunk,
                    index,
                ),

                "matched_keywords": (
                    matched
                ),

                "match_count": (
                    len(matched)
                ),

                "content": (
                    normalize_text(text)
                ),
            }
        )

    # keyword가 많이 일치하는 순
    results.sort(
        key=lambda item: (
            item[
                "match_count"
            ]
        ),
        reverse=True,
    )

    return results[:limit]


# ============================================================
# 원문 document.md 검사
# ============================================================

def search_document(
    document_path: Path,
    keywords: list[str],
    context_chars: int = 350,
    max_results: int = 5,
) -> list[dict[str, Any]]:

    if not document_path.exists():
        return []

    text = document_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    text_lower = text.lower()

    results = []

    seen_positions = set()

    for keyword in keywords:

        keyword_lower = (
            keyword.lower()
        )

        start = 0

        while True:

            position = text_lower.find(
                keyword_lower,
                start,
            )

            if position == -1:
                break

            # 같은 위치 근처 중복 방지
            bucket = (
                position // 200
            )

            if bucket not in (
                seen_positions
            ):

                seen_positions.add(
                    bucket
                )

                left = max(
                    0,
                    position
                    - context_chars,
                )

                right = min(
                    len(text),
                    position
                    + len(keyword)
                    + context_chars,
                )

                snippet = (
                    normalize_text(
                        text[
                            left:right
                        ]
                    )
                )

                matched = (
                    find_keywords(
                        snippet,
                        keywords,
                    )
                )

                results.append(
                    {
                        "keyword": keyword,
                        "matched_keywords": (
                            matched
                        ),
                        "match_count": (
                            len(matched)
                        ),
                        "snippet": snippet,
                    }
                )

            start = (
                position
                + len(keyword)
            )

    results.sort(
        key=lambda item: (
            item[
                "match_count"
            ]
        ),
        reverse=True,
    )

    return results[
        :max_results
    ]


# ============================================================
# 결과 판정
# ============================================================

def diagnose(
    raw_hits: int,
    chunk_hits: int,
) -> str:

    if (
        raw_hits == 0
        and chunk_hits == 0
    ):

        return (
            "원문/Chunk 모두 근거 없음 "
            "→ 실제 미공시 가능성"
        )

    if (
        raw_hits > 0
        and chunk_hits == 0
    ):

        return (
            "원문에는 있으나 Chunk에는 없음 "
            "→ 후보추출/청킹 Recall 문제"
        )

    if (
        raw_hits > 0
        and chunk_hits > 0
    ):

        return (
            "원문과 Chunk 모두 존재 "
            "→ BGE-M3 검색순위/query 문제 가능"
        )

    return (
        "Chunk에는 있으나 원문 위치 확인 필요"
    )


# ============================================================
# main
# ============================================================

def main():

    print()
    print(
        "=" * 80
    )

    print(
        "PEERPROOF / "
        "MISSING RISK EVIDENCE CHECK"
    )

    print(
        "=" * 80
    )

    company_name = input(
        "\n기업명을 입력하세요: "
    ).strip()

    if not company_name:

        raise ValueError(
            "기업명이 비어 있습니다."
        )

    company_dir = (
        ROOT_DIR
        / "data"
        / "processed"
        / company_name
    )

    rag_path = (
        company_dir
        / "rag"
        / "rag_chunks.json"
    )

    if not rag_path.exists():

        raise FileNotFoundError(
            f"rag_chunks.json이 없습니다:\n"
            f"{rag_path}"
        )

    # ========================================================
    # RAG chunks
    # ========================================================

    chunks = load_json(
        rag_path
    )

    if isinstance(
        chunks,
        dict,
    ):

        chunks = chunks.get(
            "chunks",
            []
        )

    print()
    print(
        f"RAG chunks: "
        f"{len(chunks)}"
    )

    # ========================================================
    # DART parsed documents
    # ========================================================

    report_paths = {

        "annual": (
            company_dir
            / "annual"
            / "document.md"
        ),

        "semiannual": (
            company_dir
            / "semiannual"
            / "document.md"
        ),

        "quarterly": (
            company_dir
            / "quarterly"
            / "document.md"
        ),
    }

    # ========================================================
    # Field별 검사
    # ========================================================

    for field_key, config in (
        TARGET_FIELDS.items()
    ):

        label = config[
            "label"
        ]

        keywords = config[
            "keywords"
        ]

        print()
        print()
        print(
            "=" * 80
        )

        print(
            f"{field_key} / {label}"
        )

        print(
            "=" * 80
        )

        # ====================================================
        # 1. RAG Chunk
        # ====================================================

        chunk_results = (
            search_rag_chunks(
                chunks=chunks,
                keywords=keywords,
                limit=5,
            )
        )

        print()
        print(
            f"[RAG CHUNK] "
            f"{len(chunk_results)}개"
        )

        if not chunk_results:

            print(
                "  검색 결과 없음"
            )

        for result in (
            chunk_results
        ):

            print()
            print(
                f"- "
                f"{result['chunk_id']}"
            )

            print(
                "  keywords:",
                result[
                    "matched_keywords"
                ],
            )

            print(
                "  ",
                result[
                    "content"
                ][
                    :300
                ],
            )

        # ====================================================
        # 2. Raw document
        # ====================================================

        total_raw_hits = 0

        print()
        print(
            "[DART DOCUMENT]"
        )

        for report_name, path in (
            report_paths.items()
        ):

            raw_results = (
                search_document(
                    document_path=path,
                    keywords=keywords,
                    max_results=3,
                )
            )

            total_raw_hits += (
                len(raw_results)
            )

            print()
            print(
                f"  {report_name}: "
                f"{len(raw_results)}개"
            )

            for result in (
                raw_results
            ):

                print(
                    "   - keywords:",
                    result[
                        "matched_keywords"
                    ],
                )

                print(
                    "     ",
                    result[
                        "snippet"
                    ][
                        :300
                    ],
                )

        # ====================================================
        # Diagnosis
        # ====================================================

        print()
        print(
            "[진단]"
        )

        print(
            diagnose(
                raw_hits=(
                    total_raw_hits
                ),
                chunk_hits=(
                    len(
                        chunk_results
                    )
                ),
            )
        )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()