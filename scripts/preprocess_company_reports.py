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


from peerproof.dart import (
    DartDocumentParser,
)


RAW_ROOT = (
    ROOT_DIR
    / "data"
    / "raw"
    / "dart"
)

PROCESSED_ROOT = (
    ROOT_DIR
    / "data"
    / "processed"
)


REPORT_TYPES = [
    "annual",
    "semiannual",
    "quarterly",
]


# ============================================================
# 유틸
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


def save_text(
    path: Path,
    text: str,
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

        file.write(text)


def find_zip_by_report_type(
    company_dir: Path,
    report_type: str,
):

    matches = list(
        company_dir.glob(
            f"*_{report_type}_*.zip"
        )
    )

    if not matches:
        return None

    matches.sort()

    return matches[-1]


# ============================================================
# 보고서 하나 처리
# ============================================================

def process_report(
    parser: DartDocumentParser,
    zip_path: Path,
    output_dir: Path,
):

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # 메인 XML / HTML 파싱
    # --------------------------------------------------------

    main_document = (
        parser.extract_main_document(
            zip_path
        )
    )

    # --------------------------------------------------------
    # Markdown 저장
    # --------------------------------------------------------

    document_path = (
        output_dir
        / "document.md"
    )

    save_text(
        document_path,
        main_document[
            "markdown"
        ],
    )

    # --------------------------------------------------------
    # 표 저장
    # --------------------------------------------------------

    tables_path = (
        output_dir
        / "tables.json"
    )

    save_json(
        tables_path,
        main_document[
            "tables"
        ],
    )

    # --------------------------------------------------------
    # ZIP 이미지 파일 추출
    # --------------------------------------------------------

    assets_dir = (
        output_dir
        / "assets"
    )

    extracted_images = (
        parser.extract_image_files(
            zip_path,
            assets_dir,
        )
    )

    # --------------------------------------------------------
    # HTML/XML의 이미지 참조정보와
    # 실제 ZIP 이미지 파일 목록을 같이 저장
    # --------------------------------------------------------

    image_metadata = {
        "document_references": (
            main_document[
                "images"
            ]
        ),
        "extracted_files": (
            extracted_images
        ),
    }

    images_path = (
        output_dir
        / "images.json"
    )

    save_json(
        images_path,
        image_metadata,
    )

    # --------------------------------------------------------
    # 보고서 metadata
    # --------------------------------------------------------

    report_metadata = {
        "source_zip": (
            zip_path.name
        ),
        "source_document": (
            main_document[
                "filename"
            ]
        ),
        "characters": len(
            main_document[
                "text"
            ]
        ),
        "table_count": len(
            main_document[
                "tables"
            ]
        ),
        "image_reference_count": len(
            main_document[
                "images"
            ]
        ),
        "image_file_count": len(
            extracted_images
        ),
        "outputs": {
            "document": (
                "document.md"
            ),
            "tables": (
                "tables.json"
            ),
            "images": (
                "images.json"
            ),
            "assets": (
                "assets/"
            ),
        },
    }

    save_json(
        output_dir
        / "metadata.json",
        report_metadata,
    )

    return report_metadata


# ============================================================
# main
# ============================================================

def main():

    print()
    print(
        "=" * 70
    )

    print(
        "PEERPROOF / STRUCTURED "
        "DART PREPROCESSOR"
    )

    print(
        "=" * 70
    )

    company_name = input(
        "\n처리할 기업명을 입력하세요: "
    ).strip()

    raw_company_dir = (
        RAW_ROOT
        / company_name
    )

    if not raw_company_dir.exists():

        print()
        print(
            "기업 원본 폴더가 없습니다."
        )

        print(
            raw_company_dir
        )

        return

    raw_metadata_path = (
        raw_company_dir
        / "metadata.json"
    )

    if not raw_metadata_path.exists():

        print(
            "metadata.json이 없습니다."
        )

        return

    raw_metadata = load_json(
        raw_metadata_path
    )

    processed_company_dir = (
        PROCESSED_ROOT
        / company_name
    )

    processed_company_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    parser = (
        DartDocumentParser()
    )

    processed_summary = {}

    # --------------------------------------------------------
    # 보고서별 처리
    # --------------------------------------------------------

    for report_type in (
        REPORT_TYPES
    ):

        print()
        print(
            f"[{report_type}] 처리 중"
        )

        zip_path = (
            find_zip_by_report_type(
                raw_company_dir,
                report_type,
            )
        )

        if zip_path is None:

            print(
                "  보고서 ZIP 없음"
            )

            processed_summary[
                report_type
            ] = None

            continue

        print(
            f"  입력: "
            f"{zip_path.name}"
        )

        output_dir = (
            processed_company_dir
            / report_type
        )

        try:

            metadata = (
                process_report(
                    parser=parser,
                    zip_path=zip_path,
                    output_dir=(
                        output_dir
                    ),
                )
            )

        except Exception as error:

            print(
                f"  처리 실패: "
                f"{error}"
            )

            processed_summary[
                report_type
            ] = None

            continue

        processed_summary[
            report_type
        ] = metadata

        print(
            f"  문자 수: "
            f"{metadata['characters']:,}"
        )

        print(
            f"  표: "
            f"{metadata['table_count']:,}개"
        )

        print(
            f"  이미지 참조: "
            f"{metadata['image_reference_count']:,}개"
        )

        print(
            f"  이미지 파일: "
            f"{metadata['image_file_count']:,}개"
        )

        print(
            f"  저장: "
            f"{output_dir}"
        )

    # --------------------------------------------------------
    # 기업 단위 전체 metadata
    # --------------------------------------------------------

    final_metadata = {
        "company": (
            raw_metadata.get(
                "company"
            )
        ),
        "collection_rule": (
            raw_metadata.get(
                "collection_rule"
            )
        ),
        "preprocessing": {
            "strategy": (
                "text + table + image "
                "structure preservation"
            ),
            "tables": (
                "JSON + Markdown"
            ),
            "images": (
                "metadata + original assets"
            ),
            "image_analysis": (
                "not performed"
            ),
        },
        "reports": (
            processed_summary
        ),
    }

    save_json(
        processed_company_dir
        / "processed_metadata.json",
        final_metadata,
    )

    # --------------------------------------------------------
    # 완료
    # --------------------------------------------------------

    print()
    print(
        "=" * 70
    )

    print(
        "구조 보존 전처리 완료"
    )

    print(
        "=" * 70
    )

    print()
    print(
        f"저장 위치:"
    )

    print(
        processed_company_dir
    )

    print()
    print(
        "다음 단계:"
    )

    print(
        "document.md + tables.json "
        "→ Business Profile 생성"
    )


if __name__ == "__main__":
    main()