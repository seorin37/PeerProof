from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


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
    DartClient,
    DartFinanceService,
)


RAW_DART_ROOT = (
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


# ============================================================
# JSON
# ============================================================

def load_json(
    path: Path,
) -> dict[str, Any]:

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
    data: Any,
) -> None:

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
# metadata 위치 탐색
# ============================================================

def find_metadata_path(
    company_name: str,
) -> Path:

    company_dir = (
        RAW_DART_ROOT
        / company_name
    )

    candidates = [
        company_dir
        / "metadata.json",

        company_dir
        / "download_metadata.json",

        company_dir
        / "selected_reports.json",
    ]

    for path in candidates:

        if path.exists():
            return path

    # 혹시 하위 폴더에 있을 경우
    recursive_candidates = list(
        company_dir.rglob(
            "metadata.json"
        )
    )

    if recursive_candidates:

        return recursive_candidates[0]

    raise FileNotFoundError(
        "\nDART metadata.json을 찾을 수 없습니다.\n"
        f"검색 위치: {company_dir}\n\n"
        "먼저 IPO 기준일 이전 보고서를 "
        "다운로드하는 스크립트를 실행해야 합니다."
    )


# ============================================================
# corp_code 찾기
# ============================================================

def extract_corp_code(
    metadata: dict[str, Any],
) -> str:

    # 가능한 metadata 구조를 모두 대응
    candidates = [
        metadata.get(
            "corp_code"
        ),

        metadata.get(
            "company",
            {}
        ).get(
            "corp_code"
        )
        if isinstance(
            metadata.get(
                "company"
            ),
            dict,
        )
        else None,

        metadata.get(
            "corp",
            {}
        ).get(
            "corp_code"
        )
        if isinstance(
            metadata.get(
                "corp"
            ),
            dict,
        )
        else None,
    ]

    for value in candidates:

        if value:

            return str(
                value
            )

    raise ValueError(
        "metadata.json에서 "
        "corp_code를 찾을 수 없습니다."
    )


# ============================================================
# 보고서 목록 추출
# ============================================================

def extract_selected_reports(
    metadata: dict[str, Any],
) -> dict[str, Any]:

    # --------------------------------------------------------
    # 형태 1
    # selected_reports: {
    #     annual: {...},
    #     semiannual: {...},
    #     quarterly: {...}
    # }
    # --------------------------------------------------------

    selected = metadata.get(
        "selected_reports"
    )

    if isinstance(
        selected,
        dict,
    ):

        return selected

    # --------------------------------------------------------
    # 형태 2
    # reports: {...}
    # --------------------------------------------------------

    reports = metadata.get(
        "reports"
    )

    if isinstance(
        reports,
        dict,
    ):

        return reports

    # --------------------------------------------------------
    # 형태 3
    # metadata 최상위에 바로 있음
    # --------------------------------------------------------

    result = {}

    aliases = {
        "annual": [
            "annual",
            "business_report",
        ],

        "semiannual": [
            "semiannual",
            "half_year",
        ],

        "quarterly": [
            "quarterly",
            "quarter",
        ],
    }

    for standard_name, keys in (
        aliases.items()
    ):

        for key in keys:

            value = metadata.get(
                key
            )

            if value:

                result[
                    standard_name
                ] = value

                break

    if result:

        return result

    raise ValueError(
        "metadata.json에서 "
        "선택된 보고서 정보를 찾을 수 없습니다."
    )


# ============================================================
# 문자열에서 연도 추출
# ============================================================

def extract_year_from_text(
    text: str,
) -> int | None:

    if not text:
        return None

    # 2022.12 / 2023.06 / 2023년 등의 형태
    match = re.search(
        r"(20\d{2})",
        text,
    )

    if not match:
        return None

    return int(
        match.group(1)
    )


# ============================================================
# 보고서 날짜 추출
# ============================================================

def extract_filing_date(
    report_data: Any,
) -> str | None:

    if not isinstance(
        report_data,
        dict,
    ):

        return None

    possible_keys = [
        "rcept_dt",
        "filing_date",
        "date",
        "report_date",
    ]

    for key in possible_keys:

        value = report_data.get(
            key
        )

        if value:

            return str(
                value
            )

    return None


# ============================================================
# 보고서명 추출
# ============================================================

def extract_report_name(
    report_data: Any,
) -> str:

    if isinstance(
        report_data,
        str,
    ):

        return report_data

    if not isinstance(
        report_data,
        dict,
    ):

        return ""

    possible_keys = [
        "report_nm",
        "report_name",
        "name",
        "title",
        "filename",
        "file_name",
    ]

    for key in possible_keys:

        value = report_data.get(
            key
        )

        if value:

            return str(
                value
            )

    return ""


# ============================================================
# ZIP 파일명 추출
# ============================================================

def extract_filename(
    report_data: Any,
) -> str:

    if isinstance(
        report_data,
        str,
    ):

        return report_data

    if not isinstance(
        report_data,
        dict,
    ):

        return ""

    possible_keys = [
        "filename",
        "file_name",
        "saved_file",
        "path",
        "zip_path",
    ]

    for key in possible_keys:

        value = report_data.get(
            key
        )

        if value:

            return str(
                value
            )

    return ""


# ============================================================
# 사업연도 판별
# ============================================================

def determine_business_year(
    report_type: str,
    report_data: Any,
) -> int:

    report_name = (
        extract_report_name(
            report_data
        )
    )

    filename = (
        extract_filename(
            report_data
        )
    )

    # --------------------------------------------------------
    # 가장 신뢰도가 높은 정보:
    # 보고서명 안의 결산기간
    #
    # 예:
    # 사업보고서 (2022.12)
    # 반기보고서 (2023.06)
    # 분기보고서 (2023.09)
    # --------------------------------------------------------

    for text in [
        report_name,
        filename,
    ]:

        matches = re.findall(
            r"(20\d{2})[.\-/년]",
            text,
        )

        if matches:

            # 파일명 앞쪽 접수일 20230329보다
            # 괄호 안 2022.12 같은 값을 우선하고 싶으므로
            # 마지막 연도를 사용
            return int(
                matches[-1]
            )

    # --------------------------------------------------------
    # fallback:
    # 접수일 이용
    # --------------------------------------------------------

    filing_date = (
        extract_filing_date(
            report_data
        )
    )

    if filing_date:

        filing_year = (
            extract_year_from_text(
                filing_date
            )
        )

        if filing_year:

            # 사업보고서는 보통 다음 해에 제출
            if report_type == "annual":

                return (
                    filing_year
                    - 1
                )

            # 반기/분기는 해당 사업연도
            return filing_year

    # --------------------------------------------------------
    # 마지막 fallback
    # --------------------------------------------------------

    combined = (
        f"{report_name} "
        f"{filename}"
    )

    year = extract_year_from_text(
        combined
    )

    if year:

        if report_type == "annual":
            return year - 1

        return year

    raise ValueError(
        f"{report_type}의 "
        "사업연도를 판별하지 못했습니다.\n"
        f"report={report_data}"
    )


# ============================================================
# quarterly 유형 판별
# ============================================================

def determine_quarterly_type(
    report_data: Any,
) -> str:

    text = (
        extract_report_name(
            report_data
        )
        + " "
        + extract_filename(
            report_data
        )
    )

    # 1분기
    if (
        "1분기" in text
        or ".03" in text
        or "-03" in text
    ):

        return "quarterly_1"

    # 3분기
    if (
        "3분기" in text
        or ".09" in text
        or "-09" in text
    ):

        return "quarterly_3"

    # 사용자가 현재 수집하는 가장 최근
    # IPO 이전 분기보고서는 대부분 3분기지만
    # 판별이 불가능하면 오류로 처리
    raise ValueError(
        "분기보고서가 1분기인지 "
        "3분기인지 판별하지 못했습니다.\n"
        f"보고서: {text}"
    )


# ============================================================
# Finance report_type 변환
# ============================================================

def convert_report_type(
    report_type: str,
    report_data: Any,
) -> str:

    if report_type == "annual":
        return "annual"

    if report_type == "semiannual":
        return "semiannual"

    if report_type == "quarterly":

        return determine_quarterly_type(
            report_data
        )

    raise ValueError(
        f"지원하지 않는 보고서 유형: "
        f"{report_type}"
    )


# ============================================================
# 재무 API 조회
# ============================================================

def download_finance_report(
    finance_service: DartFinanceService,
    company_name: str,
    corp_code: str,
    report_type: str,
    report_data: Any,
) -> dict[str, Any]:

    business_year = (
        determine_business_year(
            report_type=report_type,
            report_data=report_data,
        )
    )

    finance_report_type = (
        convert_report_type(
            report_type=report_type,
            report_data=report_data,
        )
    )

    print()
    print(
        "-" * 70
    )

    print(
        f"{report_type.upper()}"
    )

    print(
        f"사업연도        : "
        f"{business_year}"
    )

    print(
        f"DART report type: "
        f"{finance_report_type}"
    )

    # --------------------------------------------------------
    # 연결재무제표 우선
    # --------------------------------------------------------

    print(
        "연결재무제표(CFS) 조회..."
    )

    statements = (
        finance_service
        .get_financial_statements(
            corp_code=corp_code,
            business_year=business_year,
            report_type=(
                finance_report_type
            ),
            fs_div="CFS",
        )
    )

    fs_div = "CFS"

    # --------------------------------------------------------
    # 연결 없으면 별도
    # --------------------------------------------------------

    if not statements:

        print(
            "CFS 없음 "
            "→ OFS 조회"
        )

        statements = (
            finance_service
            .get_financial_statements(
                corp_code=corp_code,
                business_year=(
                    business_year
                ),
                report_type=(
                    finance_report_type
                ),
                fs_div="OFS",
            )
        )

        fs_div = "OFS"

    print(
        f"재무 계정 수    : "
        f"{len(statements)}"
    )

    # --------------------------------------------------------
    # 저장
    # --------------------------------------------------------

    finance_dir = (
        PROCESSED_ROOT
        / company_name
        / "finance"
        / "raw"
    )

    filename = (
        f"{business_year}_"
        f"{finance_report_type}_"
        f"{fs_div}.json"
    )

    output_path = (
        finance_dir
        / filename
    )

    output_data = {
        "company": (
            company_name
        ),

        "corp_code": (
            corp_code
        ),

        "business_year": (
            business_year
        ),

        "source_report_type": (
            report_type
        ),

        "dart_report_type": (
            finance_report_type
        ),

        "fs_div": (
            fs_div
        ),

        "source_report": (
            report_data
        ),

        "count": len(
            statements
        ),

        "statements": (
            statements
        ),
    }

    save_json(
        output_path,
        output_data,
    )

    print(
        f"저장: {output_path.name}"
    )

    return {
        "report_type": (
            report_type
        ),

        "business_year": (
            business_year
        ),

        "dart_report_type": (
            finance_report_type
        ),

        "fs_div": (
            fs_div
        ),

        "count": len(
            statements
        ),

        "output_path": str(
            output_path
        ),
    }


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
        "AUTO FINANCIAL STATEMENT DOWNLOADER"
    )

    print(
        "=" * 70
    )

    # ========================================================
    # 사용자 입력은 기업명 하나
    # ========================================================

    company_name = input(
        "\n기업명을 입력하세요: "
    ).strip()

    if not company_name:

        raise ValueError(
            "기업명이 비어 있습니다."
        )

    # ========================================================
    # 1. 기존 metadata 자동 탐색
    # ========================================================

    print()
    print(
        "[1/4] DART metadata 탐색"
    )

    metadata_path = (
        find_metadata_path(
            company_name
        )
    )

    print(
        f"metadata: "
        f"{metadata_path}"
    )

    metadata = load_json(
        metadata_path
    )

    # ========================================================
    # 2. corp_code 자동 획득
    # ========================================================

    print()
    print(
        "[2/4] 기업 정보 확인"
    )

    corp_code = (
        extract_corp_code(
            metadata
        )
    )

    print(
        f"기업명    : "
        f"{company_name}"
    )

    print(
        f"corp_code : "
        f"{corp_code}"
    )

    ipo_date = (
        metadata.get(
            "ipo_date"
        )
        or metadata.get(
            "reference_date"
        )
        or metadata.get(
            "cutoff_date"
        )
    )

    if ipo_date:

        print(
            f"IPO 기준일: "
            f"{ipo_date}"
        )

    # ========================================================
    # 3. IPO 이전 선택 보고서 로드
    # ========================================================

    print()
    print(
        "[3/4] IPO 이전 선택 보고서 확인"
    )

    selected_reports = (
        extract_selected_reports(
            metadata
        )
    )

    report_order = [
        "annual",
        "semiannual",
        "quarterly",
    ]

    available_reports = []

    for report_type in (
        report_order
    ):

        report_data = (
            selected_reports.get(
                report_type
            )
        )

        if not report_data:
            continue

        available_reports.append(
            (
                report_type,
                report_data,
            )
        )

        report_name = (
            extract_report_name(
                report_data
            )
        )

        print(
            f"{report_type:<12}: "
            f"{report_name}"
        )

    if not available_reports:

        raise ValueError(
            "사용 가능한 IPO 이전 "
            "정기보고서가 없습니다."
        )

    # ========================================================
    # 4. Finance 자동 다운로드
    # ========================================================

    print()
    print(
        "[4/4] 재무데이터 자동 수집"
    )

    client = DartClient()

    finance_service = (
        DartFinanceService(
            client
        )
    )

    results = []

    for (
        report_type,
        report_data,
    ) in available_reports:

        try:

            result = (
                download_finance_report(
                    finance_service=(
                        finance_service
                    ),
                    company_name=(
                        company_name
                    ),
                    corp_code=(
                        corp_code
                    ),
                    report_type=(
                        report_type
                    ),
                    report_data=(
                        report_data
                    ),
                )
            )

            results.append(
                result
            )

        except Exception as error:

            print()
            print(
                f"[WARNING] "
                f"{report_type} "
                f"Finance 조회 실패"
            )

            print(
                error
            )

            results.append(
                {
                    "report_type": (
                        report_type
                    ),
                    "status": (
                        "failed"
                    ),
                    "error": (
                        str(error)
                    ),
                }
            )

    # ========================================================
    # 요약 저장
    # ========================================================

    finance_dir = (
        PROCESSED_ROOT
        / company_name
        / "finance"
    )

    summary_path = (
        finance_dir
        / "finance_download_metadata.json"
    )

    summary = {
        "company": (
            company_name
        ),

        "corp_code": (
            corp_code
        ),

        "ipo_date": (
            ipo_date
        ),

        "source_metadata": (
            str(metadata_path)
        ),

        "reports": (
            results
        ),
    }

    save_json(
        summary_path,
        summary,
    )

    # ========================================================
    # 출력
    # ========================================================

    print()
    print(
        "=" * 70
    )

    print(
        "FINANCE 자동 수집 완료"
    )

    print(
        "=" * 70
    )

    print()

    for result in results:

        if (
            result.get(
                "status"
            )
            == "failed"
        ):

            print(
                f"❌ "
                f"{result['report_type']}"
            )

            continue

        print(
            f"✓ "
            f"{result['report_type']:<12}"
            f" year="
            f"{result['business_year']}"
            f" / "
            f"{result['fs_div']}"
            f" / "
            f"{result['count']} accounts"
        )

    print()

    print(
        "Finance metadata:"
    )

    print(
        summary_path
    )


if __name__ == "__main__":
    main()