import os
import requests
import pandas as pd

from pathlib import Path
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
# 대상 기업
# =========================================================

TARGET_CORP_NAME = "에이피알"

# 여기에 에이피알의 실제 DART corp_code 입력
TARGET_CORP_CODE = "01190568"


# =========================================================
# 전체 기간 설정
# =========================================================

START_DATE = "19990101"
END_DATE = "20261231"


# =========================================================
# DART 조회
# =========================================================

def get_apr_filings():

    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": TARGET_CORP_CODE,
        "bgn_de": START_DATE,
        "end_de": END_DATE,
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

        if data.get("status") == "013":
            break

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
            f"[{page_no}/{total_page}] "
            f"{len(items)}건 수집"
        )

        if page_no >= total_page:
            break

        page_no += 1

    return results


# =========================================================
# 실행
# =========================================================

if __name__ == "__main__":

    print("=" * 70)
    print(f"{TARGET_CORP_NAME} 증권신고서 전체 조회")
    print("=" * 70)

    filings = get_apr_filings()

    rows = []

    for item in filings:

        report_nm = item.get("report_nm", "")

        # '증권신고서(지분증권)' 포함된 공시만
        if "증권신고서(지분증권)" in report_nm:

            rows.append({
                "corp_code": item.get("corp_code"),
                "corp_name": item.get("corp_name"),
                "stock_code": item.get("stock_code"),
                "report_nm": report_nm,
                "rcept_dt": item.get("rcept_dt"),
                "rcept_no": item.get("rcept_no"),
            })

    df = pd.DataFrame(rows)

    if df.empty:

        print(
            f"{TARGET_CORP_NAME}의 "
            f"'증권신고서(지분증권)' 관련 공시가 없습니다."
        )

        exit()

    # 오래된 순
    df = df.sort_values(
        by="rcept_dt",
        ascending=True
    ).reset_index(drop=True)

    print()
    print(df.to_string(index=False))

    print()
    print(f"총 {len(df)}건")

    print()
    print(
        f"최초 접수일: {df.iloc[0]['rcept_dt']}"
    )

    print(
        f"최초 공시명: {df.iloc[0]['report_nm']}"
    )

    # 저장
    BASE_DIR = (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )

    OUTPUT_DIR = BASE_DIR / "outputs"

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        OUTPUT_DIR /
        "apr_securities_filings_all.csv"
    )

    df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print(f"저장 완료: {output_file}")