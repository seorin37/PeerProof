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
# 최근 90일 설정
# =========================================================

today = datetime.today()

RECENT_END_DATE = today.strftime("%Y%m%d")

RECENT_START_DATE = (
    today - timedelta(days=90)
).strftime("%Y%m%d")


# 과거 최초 신고서 탐색 시작일
HISTORY_START_DATE = "19990101"


# =========================================================
# DART 조회 함수
# =========================================================

def get_disclosures(
    corp_code=None,
    bgn_de=None,
    end_de=None,
    detail_type=None
):
    """
    DART 공시 목록 조회
    """

    params = {
        "crtfc_key": DART_API_KEY,
        "page_count": 100,
        "sort": "date",
        "sort_mth": "asc",
    }

    if corp_code:
        params["corp_code"] = corp_code

    if bgn_de:
        params["bgn_de"] = bgn_de

    if end_de:
        params["end_de"] = end_de

    if detail_type:
        params["pblntf_detail_ty"] = detail_type

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

        # API 오류
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
# 최근 90일 C001 전체 조회
# =========================================================

def get_recent_c001_filings():
    """
    최근 90일 동안의 C001 공시 전체 조회
    """

    return get_disclosures(
        corp_code=None,
        bgn_de=RECENT_START_DATE,
        end_de=RECENT_END_DATE,
        detail_type="C001"
    )


# =========================================================
# 특정 기업의 진짜 최초 증권신고서 찾기
# =========================================================

def get_first_securities_filing(corp_code):
    """
    특정 기업의 과거 C001 공시를 전부 조회한 뒤,
    report_nm에 '증권신고서(지분증권)'이 포함된
    가장 오래된 접수일을 찾음
    """

    filings = get_disclosures(
        corp_code=corp_code,
        bgn_de=HISTORY_START_DATE,
        end_de=RECENT_END_DATE,
        detail_type="C001"
    )

    matched = []

    for item in filings:

        report_nm = item.get("report_nm", "")

        if "증권신고서(지분증권)" in report_nm:

            matched.append(item)

    if not matched:
        return None

    # 가장 오래된 접수일
    first_filing = min(
        matched,
        key=lambda x: x["rcept_dt"]
    )

    return first_filing


# =========================================================
# 메인 실행
# =========================================================

if __name__ == "__main__":

    print("=" * 80)
    print("최근 증권신고서(지분증권) 제출 기업 탐색")
    print("=" * 80)

    print(
        f"최근 검색기간: "
        f"{RECENT_START_DATE} ~ {RECENT_END_DATE}"
    )

    print()


    # -----------------------------------------------------
    # 1. 최근 90일 C001 전체 조회
    # -----------------------------------------------------

    recent_filings = get_recent_c001_filings()

    recent_rows = []

    for item in recent_filings:

        recent_rows.append({
            "corp_code": item.get("corp_code"),
            "corp_name": item.get("corp_name"),
            "stock_code": item.get("stock_code"),
            "report_nm": item.get("report_nm"),
            "rcept_dt": item.get("rcept_dt"),
            "rcept_no": item.get("rcept_no"),
        })


    recent_df = pd.DataFrame(recent_rows)


    if recent_df.empty:

        print("최근 90일 내 C001 공시가 없습니다.")
        exit()


    print(
        f"C001 전체 공시: "
        f"{len(recent_df)}건"
    )


    # -----------------------------------------------------
    # 2. '증권신고서(지분증권)' 포함 공시만 추출
    # -----------------------------------------------------

    securities_df = recent_df[
        recent_df["report_nm"].str.contains(
            "증권신고서(지분증권)",
            na=False,
            regex=False
        )
    ].copy()


    if securities_df.empty:

        print(
            "'증권신고서(지분증권)'이 포함된 "
            "공시가 없습니다."
        )

        exit()


    print(
        f"'증권신고서(지분증권)' 포함 공시: "
        f"{len(securities_df)}건"
    )


    # -----------------------------------------------------
    # 3. 최근 90일 내 해당 공시가 있었던 기업만 추출
    # -----------------------------------------------------

    recent_companies = (
        securities_df[
            [
                "corp_code",
                "corp_name",
                "stock_code"
            ]
        ]
        .drop_duplicates(
            subset=["corp_code"]
        )
        .reset_index(drop=True)
    )


    print(
        f"최근 해당 공시 제출 기업: "
        f"{len(recent_companies)}개"
    )

    print()


    # -----------------------------------------------------
    # 4. 기업별 과거 기록 재조회
    # -----------------------------------------------------

    first_filing_results = []

    total = len(recent_companies)


    for i, row in recent_companies.iterrows():

        corp_code = row["corp_code"]
        corp_name = row["corp_name"]
        stock_code = row["stock_code"]

        print(
            f"[{i + 1}/{total}] "
            f"{corp_name} ({corp_code}) 확인 중..."
        )

        try:

            first_filing = (
                get_first_securities_filing(
                    corp_code
                )
            )

            if first_filing:

                first_filing_results.append({
                    "corp_code":
                        corp_code,

                    "corp_name":
                        corp_name,

                    "stock_code":
                        stock_code,

                    "first_report_nm":
                        first_filing.get(
                            "report_nm"
                        ),

                    "first_rcept_dt":
                        first_filing.get(
                            "rcept_dt"
                        ),

                    "first_rcept_no":
                        first_filing.get(
                            "rcept_no"
                        ),
                })

                print(
                    f"  최초 신고: "
                    f"{first_filing.get('rcept_dt')} "
                    f"| "
                    f"{first_filing.get('report_nm')}"
                )

            else:

                print(
                    "  최초 증권신고서를 "
                    "찾지 못했습니다."
                )

        except Exception as e:

            print(
                f"  ERROR: {e}"
            )

        time.sleep(0.2)


    # -----------------------------------------------------
    # 5. DataFrame 변환
    # -----------------------------------------------------

    result_df = pd.DataFrame(
        first_filing_results
    )


    if result_df.empty:

        print(
            "최종 결과가 없습니다."
        )

        exit()


    # -----------------------------------------------------
    # 6. 최근 신고 활동 정보 추가
    # -----------------------------------------------------

    latest_recent = (
        securities_df
        .sort_values(
            ["corp_code", "rcept_dt"],
            ascending=[True, False]
        )
        .drop_duplicates(
            subset=["corp_code"],
            keep="first"
        )
        [
            [
                "corp_code",
                "report_nm",
                "rcept_dt",
                "rcept_no"
            ]
        ]
        .rename(
            columns={
                "report_nm":
                    "recent_report_nm",

                "rcept_dt":
                    "recent_rcept_dt",

                "rcept_no":
                    "recent_rcept_no",
            }
        )
    )


    result_df = result_df.merge(
        latest_recent,
        on="corp_code",
        how="left"
    )


    # -----------------------------------------------------
    # 7. 최근 신고일 기준 정렬
    # -----------------------------------------------------

    result_df = result_df.sort_values(
        by="recent_rcept_dt",
        ascending=False
    ).reset_index(drop=True)


    # -----------------------------------------------------
    # 8. 결과 출력
    # -----------------------------------------------------

    print()
    print("=" * 80)
    print("최종 결과")
    print("=" * 80)


    print(
        result_df[
            [
                "corp_name",
                "stock_code",
                "first_report_nm",
                "first_rcept_dt",
                "recent_report_nm",
                "recent_rcept_dt"
            ]
        ].to_string(index=False)
    )


    print()

    print(
        f"최종 기업 수: "
        f"{len(result_df)}개"
    )


    # -----------------------------------------------------
    # 9. 저장 경로
    # -----------------------------------------------------

    BASE_DIR = (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )

    OUTPUT_DIR = (
        BASE_DIR /
        "outputs"
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    # 최근 C001 전체
    all_output_file = (
        OUTPUT_DIR /
        "recent_c001_filings_all.csv"
    )


    # 최근 증권신고서 관련 공시
    recent_securities_file = (
        OUTPUT_DIR /
        "recent_securities_filings.csv"
    )


    # 기업별 최초 신고서
    first_filings_file = (
        OUTPUT_DIR /
        "recent_companies_first_securities_filing.csv"
    )


    # -----------------------------------------------------
    # 10. CSV 저장
    # -----------------------------------------------------

    recent_df.to_csv(
        all_output_file,
        index=False,
        encoding="utf-8-sig"
    )


    securities_df.to_csv(
        recent_securities_file,
        index=False,
        encoding="utf-8-sig"
    )


    result_df.to_csv(
        first_filings_file,
        index=False,
        encoding="utf-8-sig"
    )


    print()
    print("저장 완료")
    print()

    print(
        f"① 최근 C001 전체:\n"
        f"{all_output_file}"
    )

    print()

    print(
        f"② 최근 증권신고서 관련 공시:\n"
        f"{recent_securities_file}"
    )

    print()

    print(
        f"③ 기업별 최초 증권신고서:\n"
        f"{first_filings_file}"
    )