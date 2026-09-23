import json
import os
from pathlib import Path
from datetime import datetime

import requests
import yaml
from dotenv import load_dotenv


# =========================================================
# 1. 기본 경로
# =========================================================

PROJECT_ROOT = Path("experiments/pilot_ipo")

CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "target.yaml"
)

PROCESSED_ROOT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "companies"
)


# =========================================================
# 2. 환경 변수
# =========================================================

load_dotenv(".env")

API_KEY = os.getenv("DART_API_KEY")

if not API_KEY:
    raise ValueError(
        "DART_API_KEY가 .env에 설정되어 있지 않습니다."
    )


# =========================================================
# 3. 설정 파일 읽기
# =========================================================

def load_config():
    """
    target.yaml을 읽는다.
    """

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"설정 파일을 찾을 수 없습니다: {CONFIG_PATH}"
        )

    with open(
        CONFIG_PATH,
        "r",
        encoding="utf-8"
    ) as f:
        return yaml.safe_load(f)


# =========================================================
# 4. company.json 찾기
# =========================================================

def find_company_json():
    """
    processed/companies 아래의 company.json 중
    target.yaml의 회사명과 일치하는 기업을 찾는다.
    """

    config = load_config()

    target_name = (
        config["target"]["company_name"]
    )

    if not PROCESSED_ROOT.exists():
        raise FileNotFoundError(
            f"기업 데이터 폴더가 없습니다: {PROCESSED_ROOT}"
        )

    matches = []

    for company_json in PROCESSED_ROOT.glob("*/company.json"):

        with open(
            company_json,
            "r",
            encoding="utf-8"
        ) as f:
            company = json.load(f)

        if company["company_name"] == target_name:
            matches.append(
                (company_json, company)
            )

    if len(matches) == 0:
        raise FileNotFoundError(
            f"'{target_name}'의 company.json을 찾지 못했습니다.\n"
            f"먼저 01_find_corp_code.py를 실행하세요."
        )

    if len(matches) > 1:
        raise RuntimeError(
            f"'{target_name}'에 해당하는 company.json이 여러 개입니다."
        )

    return matches[0]


# =========================================================
# 5. 날짜 변환
# =========================================================

def to_dart_date(date_string):
    """
    YYYY-MM-DD → YYYYMMDD
    """

    return datetime.strptime(
        date_string,
        "%Y-%m-%d"
    ).strftime("%Y%m%d")


# =========================================================
# 6. DART 공시 목록 조회
# =========================================================

def fetch_filings(
    corp_code,
    begin_date,
    end_date
):
    """
    OpenDART list.json API를 호출해서
    해당 기업의 공시 목록을 가져온다.
    """

    url = (
        "https://opendart.fss.or.kr/api/"
        "list.json"
    )

    params = {
        "crtfc_key": API_KEY,
        "corp_code": corp_code,
        "bgn_de": begin_date,
        "end_de": end_date,
        "page_count": 100,
    }

    response = requests.get(
        url,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    status = data.get("status")

    if status != "000":
        raise RuntimeError(
            f"DART API 오류\n"
            f"status: {status}\n"
            f"message: {data.get('message')}"
        )

    return data.get(
        "list",
        []
    )


# =========================================================
# 7. IPO 증권신고서 필터링
# =========================================================

def filter_ipo_filings(
    filings,
    analysis_as_of
):
    """
    IPO 분석에 필요한
    증권신고서(지분증권) 계열만 남긴다.

    포함 대상 예:
    - 증권신고서(지분증권)
    - [기재정정]증권신고서(지분증권)
    - [발행조건확정]증권신고서(지분증권)
    """

    cutoff = to_dart_date(
        analysis_as_of
    )

    results = []

    for filing in filings:

        report_nm = filing.get(
            "report_nm",
            ""
        )

        rcept_dt = filing.get(
            "rcept_dt",
            ""
        )

        # 분석 기준일 이후 공시는 제외
        if rcept_dt > cutoff:
            continue

        # 증권신고서이면서 지분증권인 경우만 사용
        if "증권신고서" not in report_nm:
            continue

        if "지분증권" not in report_nm:
            continue

        results.append({
            "rcept_no":
                filing["rcept_no"],

            "rcept_dt":
                rcept_dt,

            "report_nm":
                report_nm,
        })

    # 최신 → 과거 순
    results.sort(
        key=lambda x: x["rcept_dt"],
        reverse=True
    )

    return results


# =========================================================
# 8. filings.json 저장
# =========================================================

def save_filings(
    company_json_path,
    company,
    analysis_as_of,
    filings
):
    """
    기업별 폴더 안에 filings.json 저장
    """

    company_dir = (
        company_json_path.parent
    )

    output_path = (
        company_dir
        / "filings.json"
    )

    output = {

        "company": {
            "company_name":
                company["company_name"],

            "corp_code":
                company["corp_code"],

            "stock_code":
                company.get("stock_code"),
        },

        "analysis_as_of":
            analysis_as_of,

        "filings":
            filings,
    }

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    return output_path


# =========================================================
# 9. 메인
# =========================================================

def main():

    print()
    print("=" * 80)
    print("PeerProof - IPO Filing Resolver")
    print("=" * 80)
    print()

    config = load_config()

    company_json_path, company = (
        find_company_json()
    )

    company_name = (
        company["company_name"]
    )

    corp_code = (
        company["corp_code"]
    )

    analysis_as_of = (
        company["analysis_as_of"]
    )


    # -----------------------------------------------------
    # 검색 기간
    # -----------------------------------------------------

    begin_date = to_dart_date(
        config["search"]["begin_date"]
    )

    # analysis_as_of 이후 정보를 섞지 않기 위해
    # 검색 종료일은 analysis_as_of를 우선 사용
    end_date = to_dart_date(
        analysis_as_of
    )


    print(
        f"Company        : {company_name}"
    )

    print(
        f"Corp Code      : {corp_code}"
    )

    print(
        f"Analysis As Of : {analysis_as_of}"
    )

    print(
        f"Search Period  : {begin_date} ~ {end_date}"
    )

    print()


    # -----------------------------------------------------
    # DART 조회
    # -----------------------------------------------------

    all_filings = fetch_filings(
        corp_code=corp_code,
        begin_date=begin_date,
        end_date=end_date
    )


    ipo_filings = filter_ipo_filings(
        filings=all_filings,
        analysis_as_of=analysis_as_of
    )


    # -----------------------------------------------------
    # 결과 출력
    # -----------------------------------------------------

    print("IPO 관련 증권신고서")
    print("-" * 80)


    if not ipo_filings:

        print(
            "조건에 맞는 증권신고서를 찾지 못했습니다."
        )

        return


    for filing in ipo_filings:

        print(
            filing["rcept_dt"],
            "|",
            filing["report_nm"],
            "|",
            filing["rcept_no"]
        )


    # -----------------------------------------------------
    # JSON 저장
    # -----------------------------------------------------

    output_path = save_filings(
        company_json_path=company_json_path,
        company=company,
        analysis_as_of=analysis_as_of,
        filings=ipo_filings
    )


    print()
    print(
        f"저장 완료: {output_path}"
    )


if __name__ == "__main__":
    main()