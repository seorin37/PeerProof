import os
import time
import requests
import pandas as pd

from pathlib import Path
from datetime import datetime
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
# 조회 기간
# 2025년 하반기 ~ 현재
# =========================================================

START_DATE = "20250701"
END_DATE = datetime.today().strftime("%Y%m%d")


# =========================================================
# 날짜 범위를 3개월 단위로 분할
# =========================================================

def make_date_ranges(start_date, end_date):
    """
    corp_code 없이 전체 기업을 조회할 경우
    DART API 검색기간 제한 때문에
    약 3개월 단위로 나눠서 조회
    """

    start = pd.to_datetime(
        start_date,
        format="%Y%m%d"
    )

    end = pd.to_datetime(
        end_date,
        format="%Y%m%d"
    )

    ranges = []

    current_start = start

    while current_start <= end:

        current_end = min(
            current_start
            + pd.DateOffset(months=3)
            - pd.Timedelta(days=1),
            end
        )

        ranges.append(
            (
                current_start.strftime("%Y%m%d"),
                current_end.strftime("%Y%m%d")
            )
        )

        current_start = (
            current_end
            + pd.Timedelta(days=1)
        )

    return ranges


# =========================================================
# 특정 기간 C001 조회
# =========================================================

def get_c001_filings_by_period(bgn_de, end_de):

    params = {
        "crtfc_key": DART_API_KEY,
        "bgn_de": bgn_de,
        "end_de": end_de,

        # 증권신고 관련 지분증권
        "pblntf_detail_ty": "C001",

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

        print(
            f"    page {page_no}/{total_page} "
            f"- {len(items)}건"
        )

        if page_no >= total_page:
            break

        page_no += 1
        time.sleep(0.2)

    return results


# =========================================================
# 2025-07-01 ~ 현재 C001 전체 조회
# =========================================================

def get_all_c001_filings():

    date_ranges = make_date_ranges(
        START_DATE,
        END_DATE
    )

    all_results = []

    total_ranges = len(date_ranges)

    for i, (bgn_de, end_de) in enumerate(
        date_ranges,
        start=1
    ):

        print()
        print(
            f"[{i}/{total_ranges}] "
            f"{bgn_de} ~ {end_de} 조회 중..."
        )

        results = get_c001_filings_by_period(
            bgn_de,
            end_de
        )

        all_results.extend(results)

        print(
            f"  → {len(results)}건 수집"
        )

        time.sleep(0.3)

    return all_results


# =========================================================
# 실행
# =========================================================

if __name__ == "__main__":

    print("=" * 80)
    print("2025년 하반기 ~ 현재 원본 증권신고서(지분증권) 탐색")
    print("=" * 80)

    print(
        f"검색기간: {START_DATE} ~ {END_DATE}"
    )

    print()

    filings = get_all_c001_filings()


    # =====================================================
    # 필요한 컬럼만 정리
    # =====================================================

    rows = []

    for item in filings:

        rows.append({
            "corp_code": item.get("corp_code"),
            "corp_name": item.get("corp_name"),
            "stock_code": item.get("stock_code"),
            "report_nm": item.get("report_nm"),
            "rcept_dt": item.get("rcept_dt"),
            "rcept_no": item.get("rcept_no"),
        })


    df = pd.DataFrame(rows)


    if df.empty:

        print("조회된 C001 공시가 없습니다.")
        exit()


    print(
        f"C001 전체 공시: {len(df)}건"
    )


    # =====================================================
    # 정확히 '증권신고서(지분증권)'인 것만 추출
    # =====================================================

    exact_df = df[
        df["report_nm"] == "증권신고서(지분증권)"
    ].copy()


    print(
        f"정확히 '증권신고서(지분증권)'인 공시: "
        f"{len(exact_df)}건"
    )


    if exact_df.empty:

        print(
            "조건에 맞는 증권신고서가 없습니다."
        )

        exit()


    # =====================================================
    # 접수번호 중복 제거
    # =====================================================

    exact_df = exact_df.drop_duplicates(
        subset=["rcept_no"]
    )


    # =====================================================
    # 기업별 가장 이른 원본 신고서 1건만 남김
    # =====================================================

    exact_df = (
        exact_df
        .sort_values(
            ["corp_code", "rcept_dt"]
        )
        .drop_duplicates(
            subset=["corp_code"],
            keep="first"
        )
    )


    # =====================================================
    # 최신 신고 기업부터 보기 좋게 정렬
    # =====================================================

    exact_df = exact_df.sort_values(
        by="rcept_dt",
        ascending=False
    ).reset_index(drop=True)


    # =====================================================
    # 결과 출력
    # =====================================================

    print()
    print("=" * 80)
    print("최종 결과")
    print("=" * 80)

    print(
        exact_df[
            [
                "corp_name",
                "stock_code",
                "report_nm",
                "rcept_dt",
                "rcept_no"
            ]
        ].to_string(index=False)
    )

    print()

    print(
        f"최종 기업 수: "
        f"{exact_df['corp_code'].nunique()}개"
    )


    # =====================================================
    # 저장 경로
    # =====================================================

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


    output_file = (
        OUTPUT_DIR /
        "exact_securities_filings_2025H2_present.csv"
    )


    # =====================================================
    # CSV 저장
    # =====================================================

    exact_df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )


    print()
    print("저장 완료:")
    print(output_file)