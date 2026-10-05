import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

DART_API_KEY = os.getenv("DART_API_KEY")

BASE_URL = "https://opendart.fss.or.kr/api/list.json"


def get_disclosures(
    corp_code,
    bgn_de="20000101",
    end_de="20261231",
    detail_type=None
):
    """
    특정 기업의 DART 공시 목록 조회
    """
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_count": 100,
        "sort": "date",
        "sort_mth": "asc"
    }

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
        data = response.json()

        # 조회 결과 없음
        if data.get("status") == "013":
            break

        if data.get("status") != "000":
            print(
                f"[ERROR] {corp_code}: "
                f"{data.get('status')} / {data.get('message')}"
            )
            break

        results.extend(data.get("list", []))

        total_page = int(data.get("total_page", 1))

        if page_no >= total_page:
            break

        page_no += 1
        time.sleep(0.1)

    return results


def check_pre_ipo_reports(corp_code):
    """
    최초 증권신고서(지분증권) 이전에
    사업보고서 또는 분기보고서가 존재하는지 확인
    """

    # 1. 증권신고서(지분증권) 조회
    securities_reports = get_disclosures(
        corp_code,
        detail_type="C001"
    )

    # 증권신고서 자체가 없으면 제외
    if not securities_reports:
        return None

    # 최초 증권신고서
    first_securities_report = min(
        securities_reports,
        key=lambda x: x["rcept_dt"]
    )

    ipo_date = first_securities_report["rcept_dt"]
    ipo_rcept_no = first_securities_report["rcept_no"]
    corp_name = first_securities_report["corp_name"]

    # 2. 사업보고서 조회
    annual_reports = get_disclosures(
        corp_code,
        end_de=ipo_date,
        detail_type="A001"
    )

    # 3. 분기보고서 조회
    quarterly_reports = get_disclosures(
        corp_code,
        end_de=ipo_date,
        detail_type="A003"
    )

    # 증권신고서 당일 제출 보고서는 제외하고
    # 반드시 이전 날짜만 사용
    annual_before = [
        x for x in annual_reports
        if x["rcept_dt"] < ipo_date
    ]

    quarterly_before = [
        x for x in quarterly_reports
        if x["rcept_dt"] < ipo_date
    ]

    # 사업보고서 / 분기보고서가 하나라도 있으면 통과
    if not annual_before and not quarterly_before:
        return None

    return {
        "corp_code": corp_code,
        "corp_name": corp_name,

        "first_securities_date": ipo_date,
        "first_securities_rcept_no": ipo_rcept_no,

        "annual_report_count": len(annual_before),
        "quarterly_report_count": len(quarterly_before),

        "annual_reports": [
            {
                "report_nm": x["report_nm"],
                "rcept_dt": x["rcept_dt"],
                "rcept_no": x["rcept_no"]
            }
            for x in annual_before
        ],

        "quarterly_reports": [
            {
                "report_nm": x["report_nm"],
                "rcept_dt": x["rcept_dt"],
                "rcept_no": x["rcept_no"]
            }
            for x in quarterly_before
        ]
    }


def filter_companies(corp_codes):
    """
    여러 기업을 대상으로 필터링
    """

    results = []

    total = len(corp_codes)

    for i, corp_code in enumerate(corp_codes, 1):

        print(f"[{i}/{total}] {corp_code} 확인 중...")

        try:
            result = check_pre_ipo_reports(corp_code)

            if result:
                results.append(result)

                print(
                    f"  ✓ {result['corp_name']} "
                    f"| 증권신고서: {result['first_securities_date']} "
                    f"| 사업보고서: {result['annual_report_count']} "
                    f"| 분기보고서: {result['quarterly_report_count']}"
                )

            else:
                print("  ✗ 조건 불충족")

        except Exception as e:
            print(f"  ERROR: {e}")

        # DART API 요청 과다 방지
        time.sleep(0.2)

    return results


if __name__ == "__main__":

    # 예시
    corp_codes = [
        "00126380",
        "00164779",
        "00164742"
    ]

    results = filter_companies(corp_codes)

    # DataFrame 변환
    df = pd.DataFrame([
        {
            "corp_code": x["corp_code"],
            "corp_name": x["corp_name"],
            "first_securities_date": x["first_securities_date"],
            "first_securities_rcept_no": x["first_securities_rcept_no"],
            "annual_report_count": x["annual_report_count"],
            "quarterly_report_count": x["quarterly_report_count"]
        }
        for x in results
    ])

    print("\n===== 최종 필터링 결과 =====")
    print(df)

    # CSV 저장
    df.to_csv(
        "companies_with_reports_before_securities.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print(
        "\n저장 완료: "
        "companies_with_reports_before_securities.csv"
    )