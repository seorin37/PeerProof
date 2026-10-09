import json
import sys
from datetime import datetime
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
    CorpCodeService,
    DisclosureService,
    DisclosureDownloader,
)


# ============================================================
# 설정
# ============================================================

# 충분한 과거 데이터를 검색하기 위한 기본 시작일
DEFAULT_START_DATE = "20180101"

RAW_DATA_DIR = (
    ROOT_DIR
    / "data"
    / "raw"
    / "dart"
)


# ============================================================
# 입력 검증
# ============================================================

def validate_date(
    date_text: str,
):
    """
    YYYYMMDD 형식 검증.
    """

    try:

        datetime.strptime(
            date_text,
            "%Y%m%d",
        )

        return True

    except ValueError:

        return False


# ============================================================
# JSON 저장
# ============================================================

def save_metadata(
    company_name: str,
    metadata: dict,
):
    """
    어떤 기준으로 데이터를 수집했는지
    metadata.json으로 함께 저장.
    """

    company_dir = (
        RAW_DATA_DIR
        / company_name
    )

    company_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        company_dir
        / "metadata.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metadata,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return output_path


# ============================================================
# main
# ============================================================

def main():

    print()
    print("=" * 70)
    print("PEERPROOF / DART DATA COLLECTOR")
    print("=" * 70)

    # --------------------------------------------------------
    # 1. 사용자 입력
    # --------------------------------------------------------

    company_name = input(
        "\n대상 기업명을 입력하세요: "
    ).strip()

    if not company_name:

        print(
            "기업명을 입력해야 합니다."
        )

        return

    stock_code = input(
        "종목코드를 입력하세요 "
        "(미상장 기업은 비워 두면 기업명으로 찾습니다): "
    ).strip()

    corp_code_input = input(
        "DART 고유번호(corp_code 8자리)를 입력하세요 "
        "(모르면 비워 두세요): "
    ).strip()

    ipo_date = input(
        "IPO 기준일을 입력하세요 (YYYYMMDD): "
    ).strip()

    if not validate_date(
        ipo_date
    ):

        print(
            "날짜 형식이 잘못되었습니다."
        )

        print(
            "예: 20231222"
        )

        return

    # --------------------------------------------------------
    # 2. IPO cutoff 계산
    # --------------------------------------------------------

    disclosure_service = (
        DisclosureService()
    )

    cutoff_date = (
        disclosure_service
        .get_cutoff_date(
            ipo_date
        )
    )

    print()
    print("-" * 70)

    print(
        f"대상기업      : {company_name}"
    )

    print(
        f"종목코드      : {stock_code or '(없음: 기업명으로 검색)'}"
    )

    print(
        f"IPO 기준일    : {ipo_date}"
    )

    print(
        f"사용 가능 공시: "
        f"{DEFAULT_START_DATE} ~ {cutoff_date}"
    )

    print(
        "(IPO 기준일 당일 및 이후 공시는 사용하지 않습니다.)"
    )

    # --------------------------------------------------------
    # 3. DART 기업 검색
    # --------------------------------------------------------

    print()
    print(
        "[1/4] DART 기업 검색"
    )

    corp_service = (
        CorpCodeService()
    )

    target_company = (
        corp_service.find_exact_company(
            corp_name=company_name,
            stock_code=stock_code,
            corp_code=corp_code_input or None,
        )
    )

    if target_company is None:

        print()
        print(
            "기업을 찾지 못했습니다."
        )

        print(
            "기업명과 종목코드를 "
            "확인하세요. 종목코드 없이 찾는 경우 "
            "기업명이 DART에 정확히 하나만 "
            "있어야 합니다."
        )

        return

    print(
        "기업 확인 완료"
    )

    print(
        f"corp_name  : "
        f"{target_company['corp_name']}"
    )

    print(
        f"corp_code  : "
        f"{target_company['corp_code']}"
    )

    print(
        f"stock_code : "
        f"{target_company['stock_code']}"
    )

    corp_code = (
        target_company[
            "corp_code"
        ]
    )

    # --------------------------------------------------------
    # 4. IPO 이전 정기보고서 검색
    # --------------------------------------------------------

    print()
    print(
        "[2/4] IPO 이전 정기보고서 검색"
    )

    reports = (
        disclosure_service
        .get_periodic_reports(
            corp_code=corp_code,
            start_date=DEFAULT_START_DATE,
            ipo_date=ipo_date,
        )
    )

    if not reports:

        print(
            "해당 기간에 "
            "사업/반기/분기보고서가 없습니다."
        )

        return

    print(
        f"검색된 정기보고서: "
        f"{len(reports)}건"
    )

    print()

    for report in reports:

        print(
            f"{report.get('rcept_dt')} | "
            f"{report.get('report_type'):10} | "
            f"{report.get('report_nm')}"
        )

    # --------------------------------------------------------
    # 5. 최신 보고서 각각 하나 선택
    # --------------------------------------------------------

    print()
    print(
        "[3/4] 기준일 이전 최신 보고서 선정"
    )

    selected = (
        disclosure_service
        .select_latest_reports(
            reports
        )
    )

    labels = {
        "annual": "사업보고서",
        "semiannual": "반기보고서",
        "quarterly": "분기보고서",
    }

    print()

    for report_type, label in (
        labels.items()
    ):

        report = selected[
            report_type
        ]

        if report is None:

            print(
                f"{label:<8}: 없음"
            )

            continue

        print(
            f"{label:<8}: "
            f"{report.get('rcept_dt')} | "
            f"{report.get('report_nm')} | "
            f"{report.get('rcept_no')}"
        )

    # --------------------------------------------------------
    # 6. 다운로드
    # --------------------------------------------------------

    print()
    print(
        "[4/4] DART 공시 원문 다운로드"
    )

    downloader = (
        DisclosureDownloader(
            output_root=RAW_DATA_DIR
        )
    )

    downloaded = {}

    for report_type, report in (
        selected.items()
    ):

        if report is None:
            continue

        try:

            output_path = (
                downloader
                .download_document(
                    rcept_no=report[
                        "rcept_no"
                    ],
                    company_name=target_company[
                        "corp_name"
                    ],
                    report_type=report_type,
                    report_name=report[
                        "report_nm"
                    ],
                    rcept_date=report[
                        "rcept_dt"
                    ],
                )
            )

            downloaded[
                report_type
            ] = str(
                output_path
            )

            print(
                f"✓ {labels[report_type]}"
            )

            print(
                f"  {output_path}"
            )

        except Exception as error:

            print(
                f"✗ {labels[report_type]} "
                f"다운로드 실패"
            )

            print(
                f"  {error}"
            )

    # --------------------------------------------------------
    # 7. metadata 저장
    # --------------------------------------------------------

    metadata = {
        "company": {
            "corp_name": target_company[
                "corp_name"
            ],
            "corp_code": corp_code,
            "stock_code": target_company[
                "stock_code"
            ],
        },

        "collection_rule": {
            "ipo_date": ipo_date,
            "cutoff_date": cutoff_date,
            "start_date": DEFAULT_START_DATE,
            "rule": (
                "IPO 기준일 이전에 "
                "DART에 공개된 정기보고서만 사용"
            ),
        },

        "selected_reports": {
            report_type: (
                {
                    "report_name": report.get(
                        "report_nm"
                    ),
                    "rcept_no": report.get(
                        "rcept_no"
                    ),
                    "rcept_date": report.get(
                        "rcept_dt"
                    ),
                }
                if report
                else None
            )
            for (
                report_type,
                report
            )
            in selected.items()
        },

        "downloaded_files": (
            downloaded
        ),
    }

    metadata_path = (
        save_metadata(
            company_name=target_company[
                "corp_name"
            ],
            metadata=metadata,
        )
    )

    # --------------------------------------------------------
    # 완료
    # --------------------------------------------------------

    print()
    print("=" * 70)

    print(
        "DART 데이터 수집 완료"
    )

    print("=" * 70)

    print(
        f"\n저장 위치:\n"
        f"{RAW_DATA_DIR / target_company['corp_name']}"
    )

    print(
        f"\nMetadata:\n"
        f"{metadata_path}"
    )

    print()

    print(
        "다음 단계:"
    )

    print(
        "DART ZIP/XML 파싱 "
        "→ AI용 텍스트 정제"
    )


if __name__ == "__main__":
    main()