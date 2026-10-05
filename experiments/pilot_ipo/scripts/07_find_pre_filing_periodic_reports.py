import os
import time
import requests
import pandas as pd

from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv


# =========================================================
# 환경변수
# =========================================================

load_dotenv()

DART_API_KEY = os.getenv("DART_API_KEY")

if not DART_API_KEY:
    raise ValueError(
        "DART_API_KEY가 없습니다. .env 파일을 확인해주세요."
    )

BASE_URL = "https://opendart.fss.or.kr/api/list.json"


# =========================================================
# 경로 설정
# =========================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

OUTPUT_DIR = BASE_DIR / "outputs"

INPUT_FILE = (
    OUTPUT_DIR /
    "exact_securities_filings_2025H2_present.csv"
)

OUTPUT_FILE = (
    OUTPUT_DIR /
    "companies_with_pre_filing_periodic_reports.csv"
)

DETAIL_OUTPUT_FILE = (
    OUTPUT_DIR /
    "pre_filing_periodic_reports_detail.csv"
)


# =========================================================
# 조회할 정기보고서 유형
# =========================================================

REPORT_TYPES = {
    "A001": "사업보고서",
    "A002": "반기보고서",
    "A003": "분기보고서",
}


# =========================================================
# DART 공시 조회
# =========================================================

def get_disclosures(
    corp_code,
    bgn_de,
    end_de,
    detail_type
):
    """
    특정 기업의 특정 유형 공시 조회
    """

    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "pblntf_detail_ty": detail_type,
        "page_count": 100,
        "sort": "date",
        "sort_mth": "asc",
    }

    results = []
    page_no = 1

    while True:

        params["page_no"] = page_no

        response = requests.get(
            BASE_URL,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        # 조회 결과 없음
        if data.get("status") == "013":
            break

        # 오류
        if data.get("status") != "000":
            raise RuntimeError(
                f"DART API 오류: "
                f"{data.get('status')} / "
                f"{data.get('message')}"
            )

        items = data.get("list", [])

        results.extend(items)

        total_page = int(
            data.get("total_page", 1)
        )

        if page_no >= total_page:
            break

        page_no += 1

        time.sleep(0.1)

    return results


# =========================================================
# 증권신고서 날짜 하루 전 계산
# =========================================================

def get_previous_date(rcept_dt):
    """
    예:
    20260115 -> 20260114
    """

    filing_date = datetime.strptime(
        str(rcept_dt),
        "%Y%m%d"
    )

    previous_date = (
        filing_date - timedelta(days=1)
    )

    return previous_date.strftime(
        "%Y%m%d"
    )


# =========================================================
# 특정 기업의 증권신고서 이전 정기보고서 조회
# =========================================================

def find_pre_filing_reports(
    corp_code,
    securities_date
):
    """
    증권신고서 접수일보다 이전에 제출된
    사업/반기/분기보고서를 모두 조회
    """

    end_date = get_previous_date(
        securities_date
    )

    # DART 과거 검색 시작일
    start_date = "19990101"

    all_reports = []

    counts = {
        "사업보고서": 0,
        "반기보고서": 0,
        "분기보고서": 0,
    }

    for detail_type, type_name in REPORT_TYPES.items():

        reports = get_disclosures(
            corp_code=corp_code,
            bgn_de=start_date,
            end_de=end_date,
            detail_type=detail_type
        )

        counts[type_name] = len(reports)

        for report in reports:

            all_reports.append({
                "report_type": type_name,
                "report_nm": report.get("report_nm"),
                "rcept_dt": report.get("rcept_dt"),
                "rcept_no": report.get("rcept_no"),
            })

        time.sleep(0.15)

    # 오래된 순 정렬
    all_reports = sorted(
        all_reports,
        key=lambda x: x["rcept_dt"]
    )

    return counts, all_reports


# =========================================================
# 실행
# =========================================================

if __name__ == "__main__":

    print("=" * 80)
    print("증권신고서 이전 정기보고서 존재 여부 확인")
    print("=" * 80)

    print()

    # -----------------------------------------------------
    # 1. 증권신고서 기업 목록 읽기
    # -----------------------------------------------------

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"입력 파일을 찾을 수 없습니다:\n"
            f"{INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE,
        dtype={
            "corp_code": str,
            "stock_code": str,
            "rcept_dt": str,
            "rcept_no": str,
        }
    )

    print(
        f"입력 기업 수: {len(df)}개"
    )

    print()


    # -----------------------------------------------------
    # 2. 기업별 검사
    # -----------------------------------------------------

    company_results = []
    detail_results = []

    total = len(df)


    for idx, row in df.iterrows():

        corp_code = str(
            row["corp_code"]
        ).zfill(8)

        corp_name = row["corp_name"]

        stock_code = row.get(
            "stock_code",
            ""
        )

        securities_date = str(
            row["rcept_dt"]
        )

        securities_rcept_no = str(
            row["rcept_no"]
        )


        print(
            f"[{idx + 1}/{total}] "
            f"{corp_name}"
        )

        print(
            f"  증권신고서 접수일: "
            f"{securities_date}"
        )


        try:

            counts, reports = (
                find_pre_filing_reports(
                    corp_code,
                    securities_date
                )
            )


            annual_count = counts[
                "사업보고서"
            ]

            semiannual_count = counts[
                "반기보고서"
            ]

            quarterly_count = counts[
                "분기보고서"
            ]


            total_count = (
                annual_count
                + semiannual_count
                + quarterly_count
            )


            # ---------------------------------------------
            # 정기보고서 존재 여부
            # ---------------------------------------------

            has_pre_report = (
                total_count > 0
            )


            # ---------------------------------------------
            # 증권신고서 직전 가장 최근 정기보고서
            # ---------------------------------------------

            if reports:

                latest_report = max(
                    reports,
                    key=lambda x: x["rcept_dt"]
                )

                latest_report_type = (
                    latest_report[
                        "report_type"
                    ]
                )

                latest_report_nm = (
                    latest_report[
                        "report_nm"
                    ]
                )

                latest_report_date = (
                    latest_report[
                        "rcept_dt"
                    ]
                )

                latest_report_rcept_no = (
                    latest_report[
                        "rcept_no"
                    ]
                )

            else:

                latest_report_type = None
                latest_report_nm = None
                latest_report_date = None
                latest_report_rcept_no = None


            # ---------------------------------------------
            # 기업 단위 결과
            # ---------------------------------------------

            company_results.append({

                "corp_code":
                    corp_code,

                "corp_name":
                    corp_name,

                "stock_code":
                    stock_code,

                "securities_rcept_dt":
                    securities_date,

                "securities_rcept_no":
                    securities_rcept_no,

                "has_pre_periodic_report":
                    has_pre_report,

                "annual_report_count":
                    annual_count,

                "semiannual_report_count":
                    semiannual_count,

                "quarterly_report_count":
                    quarterly_count,

                "total_pre_report_count":
                    total_count,

                "latest_pre_report_type":
                    latest_report_type,

                "latest_pre_report_nm":
                    latest_report_nm,

                "latest_pre_report_dt":
                    latest_report_date,

                "latest_pre_report_rcept_no":
                    latest_report_rcept_no,
            })


            # ---------------------------------------------
            # 상세 보고서 결과
            # ---------------------------------------------

            for report in reports:

                detail_results.append({

                    "corp_code":
                        corp_code,

                    "corp_name":
                        corp_name,

                    "stock_code":
                        stock_code,

                    "securities_rcept_dt":
                        securities_date,

                    "report_type":
                        report["report_type"],

                    "report_nm":
                        report["report_nm"],

                    "report_rcept_dt":
                        report["rcept_dt"],

                    "report_rcept_no":
                        report["rcept_no"],
                })


            # ---------------------------------------------
            # 터미널 출력
            # ---------------------------------------------

            if has_pre_report:

                print(
                    "  [PASS] 이전 정기보고서 존재"
                )

                print(
                    f"    사업보고서: "
                    f"{annual_count}건"
                )

                print(
                    f"    반기보고서: "
                    f"{semiannual_count}건"
                )

                print(
                    f"    분기보고서: "
                    f"{quarterly_count}건"
                )

                print(
                    f"    직전 보고서: "
                    f"{latest_report_type} "
                    f"({latest_report_date})"
                )

            else:

                print(
                    "  [FAIL] 이전 정기보고서 없음"
                )


        except Exception as e:

            print(
                f"  [ERROR] {e}"
            )


        print()

        time.sleep(0.2)


    # =====================================================
    # 3. 기업 단위 결과 DataFrame
    # =====================================================

    result_df = pd.DataFrame(
        company_results
    )


    # =====================================================
    # 4. 정기보고서가 있는 기업만 필터링
    # =====================================================

    qualified_df = result_df[
        result_df[
            "has_pre_periodic_report"
        ] == True
    ].copy()


    # 증권신고서 최신순
    qualified_df = (
        qualified_df
        .sort_values(
            "securities_rcept_dt",
            ascending=False
        )
        .reset_index(drop=True)
    )


    # =====================================================
    # 5. 상세 보고서 DataFrame
    # =====================================================

    detail_df = pd.DataFrame(
        detail_results
    )


    if not detail_df.empty:

        detail_df = (
            detail_df
            .sort_values(
                [
                    "securities_rcept_dt",
                    "corp_name",
                    "report_rcept_dt"
                ],
                ascending=[
                    False,
                    True,
                    False
                ]
            )
            .reset_index(drop=True)
        )


    # =====================================================
    # 6. 결과 출력
    # =====================================================

    print("=" * 80)
    print("최종 결과")
    print("=" * 80)

    print(
        f"전체 증권신고서 기업: "
        f"{len(result_df)}개"
    )

    print(
        f"이전 정기보고서가 있는 기업: "
        f"{len(qualified_df)}개"
    )

    print(
        f"이전 정기보고서가 없는 기업: "
        f"{len(result_df) - len(qualified_df)}개"
    )


    if not qualified_df.empty:

        print()
        print(
            qualified_df[
                [
                    "corp_name",
                    "stock_code",
                    "securities_rcept_dt",
                    "annual_report_count",
                    "semiannual_report_count",
                    "quarterly_report_count",
                    "latest_pre_report_type",
                    "latest_pre_report_dt"
                ]
            ].to_string(index=False)
        )


    # =====================================================
    # 7. CSV 저장
    # =====================================================

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    qualified_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )


    detail_df.to_csv(
        DETAIL_OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )


    print()
    print("=" * 80)
    print("저장 완료")
    print("=" * 80)

    print()
    print(
        "① 조건을 만족하는 기업 목록:"
    )
    print(
        OUTPUT_FILE
    )

    print()
    print(
        "② 증권신고서 이전 정기보고서 상세:"
    )
    print(
        DETAIL_OUTPUT_FILE
    )