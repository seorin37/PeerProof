import json
import sys
from pathlib import Path


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
    ProfileRAGChunker,
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


def save_json(
    path: Path,
    data,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
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
        "RAG CHUNK BUILDER"
    )

    print(
        "=" * 70
    )

    company_name = input(
        "\n기업명을 입력하세요: "
    ).strip()

    company_dir = (
        PROCESSED_ROOT
        / company_name
    )

    profile_dir = (
        company_dir
        / "profile"
    )

    evidence_path = (
        profile_dir
        / "profile_evidence.json"
    )

    if not evidence_path.exists():

        print()
        print(
            "profile_evidence.json이 없습니다."
        )

        print(
            "먼저 실행하세요:"
        )

        print(
            "python "
            "scripts/build_business_profile.py"
        )

        return

    # --------------------------------------------------------
    # Evidence 로드
    # --------------------------------------------------------

    print()
    print(
        "[1/3] Profile Evidence 로드"
    )

    profile_evidence = (
        load_json(
            evidence_path
        )
    )

    # --------------------------------------------------------
    # Chunk 생성
    # --------------------------------------------------------

    print(
        "[2/3] RAG Chunk 생성"
    )

    rag_data = (
        ProfileRAGChunker
        .build_chunks(
            profile_evidence
        )
    )

    # --------------------------------------------------------
    # 저장
    # --------------------------------------------------------

    rag_dir = (
        company_dir
        / "rag"
    )

    output_path = (
        rag_dir
        / "rag_chunks.json"
    )

    save_json(
        output_path,
        rag_data,
    )

    # --------------------------------------------------------
    # 통계
    # --------------------------------------------------------

    stats = (
        rag_data[
            "statistics"
        ]
    )

    print()
    print(
        "[3/3] 생성 결과"
    )

    print()

    print(
        f"전체 chunk       : "
        f"{stats['total_chunks']}"
    )

    print(
        f"중복 제거        : "
        f"{stats['duplicates_removed']}"
    )

    print()

    print(
        "Category:"
    )

    for (
        category,
        count,
    ) in stats[
        "by_category"
    ].items():

        print(
            f"  {category:<12}"
            f"{count:>4}"
        )

    print()

    print(
        "Source type:"
    )

    for (
        source_type,
        count,
    ) in stats[
        "by_source_type"
    ].items():

        print(
            f"  {source_type:<12}"
            f"{count:>4}"
        )

    print()

    print(
        "Report type:"
    )

    for (
        report_type,
        count,
    ) in stats[
        "by_report_type"
    ].items():

        print(
            f"  {report_type:<12}"
            f"{count:>4}"
        )

    print()
    print(
        "=" * 70
    )

    print(
        "RAG Chunk 생성 완료"
    )

    print(
        "=" * 70
    )

    print()

    print(
        "저장:"
    )

    print(
        output_path
    )

    print()

    print(
        "다음 단계:"
    )

    print(
        "rag_chunks.json "
        "→ BGE-M3 embedding"
    )


if __name__ == "__main__":
    main()