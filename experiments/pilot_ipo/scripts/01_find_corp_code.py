import io
import json
import os
import zipfile
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv
from bs4 import BeautifulSoup


# =========================================================
# 1. 경로 설정
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
        config = yaml.safe_load(f)

    return config


# =========================================================
# 4. DART 기업코드 다운로드
# =========================================================

def download_corp_codes():
    """
    OpenDART corpCode.xml API 호출.

    실제 응답은 ZIP 파일이며,
    ZIP 안의 CORPCODE.xml을 읽는다.
    """

    url = (
        "https://opendart.fss.or.kr/api/"
        "corpCode.xml"
    )

    params = {
        "crtfc_key": API_KEY
    }

    response = requests.get(
        url,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    return response.content


# =========================================================
# 5. ZIP 내부 XML 파싱
# =========================================================

def parse_corp_codes(zip_bytes):
    """
    ZIP → CORPCODE.xml → 기업 목록
    """

    with zipfile.ZipFile(
        io.BytesIO(zip_bytes)
    ) as zf:

        xml_names = [
            name
            for name in zf.namelist()
            if name.lower().endswith(".xml")
        ]

        if not xml_names:
            raise RuntimeError(
                "DART 응답 ZIP에서 XML을 찾지 못했습니다."
            )

        xml_data = zf.read(
            xml_names[0]
        )

    soup = BeautifulSoup(
        xml_data,
        "lxml-xml"
    )

    companies = []

    for item in soup.find_all("list"):

        corp_code = item.corp_code.get_text(
            strip=True
        )

        corp_name = item.corp_name.get_text(
            strip=True
        )

        stock_code = item.stock_code.get_text(
            strip=True
        )

        modify_date = item.modify_date.get_text(
            strip=True
        )

        companies.append({
            "corp_code": corp_code,
            "corp_name": corp_name,
            "stock_code": stock_code or None,
            "modify_date": modify_date,
        })

    return companies


# =========================================================
# 6. 회사 검색
# =========================================================

def find_company(
    companies,
    target_name
):
    """
    1순위:
        회사명 정확히 일치

    2순위:
        정확히 일치하지 않으면
        target_name 포함 기업 출력
    """

    exact_matches = [
        company
        for company in companies
        if company["corp_name"] == target_name
    ]

    if len(exact_matches) == 1:
        return exact_matches[0]

    if len(exact_matches) > 1:
        raise RuntimeError(
            f"정확히 일치하는 기업이 여러 개입니다: {target_name}"
        )

    partial_matches = [
        company
        for company in companies
        if target_name in company["corp_name"]
    ]

    if not partial_matches:
        return None

    print()
    print(
        f"'{target_name}'과 정확히 일치하는 기업은 없지만 "
        f"다음 후보를 찾았습니다."
    )

    print("-" * 80)

    for company in partial_matches:
        print(company)

    return None


# =========================================================
# 7. company.json 저장
# =========================================================

def save_company(
    company,
    analysis_as_of
):
    """
    corp_code 기준 기업 디렉터리를 만들고
    company.json 저장
    """

    corp_code = company["corp_code"]

    company_dir = (
        PROCESSED_ROOT
        / corp_code
    )

    company_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = (
        company_dir
        / "company.json"
    )

    output = {
        "company_name":
            company["corp_name"],

        "corp_code":
            company["corp_code"],

        "stock_code":
            company["stock_code"],

        "dart_modify_date":
            company["modify_date"],

        "analysis_as_of":
            analysis_as_of,
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
# 8. 메인
# =========================================================

def main():

    config = load_config()

    target_name = (
        config["target"]["company_name"]
    )

    analysis_as_of = (
        config["target"]["analysis_as_of"]
    )

    print()
    print("=" * 80)
    print("PeerProof - Company Resolver")
    print("=" * 80)

    print(
        f"검색 기업: {target_name}"
    )

    print()

    zip_bytes = download_corp_codes()

    companies = parse_corp_codes(
        zip_bytes
    )

    company = find_company(
        companies=companies,
        target_name=target_name
    )

    if company is None:

        print()
        print(
            "기업을 하나로 확정하지 못했습니다."
        )

        return

    print("기업 확인 완료")
    print("-" * 80)

    print(
        f"회사명     : {company['corp_name']}"
    )

    print(
        f"corp_code  : {company['corp_code']}"
    )

    print(
        f"stock_code : {company['stock_code']}"
    )

    output_path = save_company(
        company=company,
        analysis_as_of=analysis_as_of
    )

    print()
    print(
        f"저장 완료: {output_path}"
    )


if __name__ == "__main__":
    main()
