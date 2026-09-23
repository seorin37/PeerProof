import json
import os
import zipfile
from pathlib import Path

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

RAW_ROOT = (
    PROJECT_ROOT
    / "data"
    / "raw"
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
# 4. 현재 대상 기업의 company.json 찾기
# =========================================================

def find_company_json():
    """
    target.yaml의 company_name과 일치하는
    company.json을 찾는다.
    """

    config = load_config()

    target_name = (
        config["target"]["company_name"]
    )

    matches = []

    for company_json in PROCESSED_ROOT.glob(
        "*/company.json"
    ):

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
# 5. filings.json 읽기
# =========================================================

def load_filings(
    company_json_path
):
    """
    company.json과 같은 기업 폴더에 있는
    filings.json을 읽는다.
    """

    filings_path = (
        company_json_path.parent
        / "filings.json"
    )

    if not filings_path.exists():
        raise FileNotFoundError(
            f"filings.json을 찾을 수 없습니다.\n"
            f"경로: {filings_path}\n"
            f"먼저 02_find_ipo_filing.py를 실행하세요."
        )

    with open(
        filings_path,
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)

    return data, filings_path


# =========================================================
# 6. 단일 신고서 다운로드
# =========================================================

def download_filing(
    rcept_no,
    output_dir
):
    """
    DART document.xml API로
    하나의 신고서 원문 ZIP을 다운로드한다.
    """

    url = (
        "https://opendart.fss.or.kr/api/"
        "document.xml"
    )

    params = {
        "crtfc_key": API_KEY,
        "rcept_no": rcept_no,
    }

    response = requests.get(
        url,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    zip_path = (
        output_dir
        / f"{rcept_no}.zip"
    )

    with open(
        zip_path,
        "wb"
    ) as f:
        f.write(
            response.content
        )

    return zip_path


# =========================================================
# 7. ZIP 압축 해제
# =========================================================

def extract_filing(
    zip_path,
    extract_dir
):
    """
    ZIP 파일을 신고서 접수번호별 폴더에 해제한다.
    """

    extract_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    try:
        with zipfile.ZipFile(
            zip_path,
            "r"
        ) as zf:

            zf.extractall(
                extract_dir
            )

    except zipfile.BadZipFile:
        raise RuntimeError(
            f"다운로드한 파일이 정상적인 ZIP이 아닙니다: {zip_path}"
        )


# =========================================================
# 8. 이미 다운로드했는지 확인
# =========================================================

def already_downloaded(
    extract_dir
):
    """
    접수번호 폴더 안에 XML 파일이 이미 있으면
    재다운로드하지 않는다.
    """

    if not extract_dir.exists():
        return False

    xml_files = list(
        extract_dir.glob("*.xml")
    )

    return len(xml_files) > 0


# =========================================================
# 9. 메인
# =========================================================

def main():

    print()
    print("=" * 80)
    print("PeerProof - IPO Filing Downloader")
    print("=" * 80)
    print()

    company_json_path, company = (
        find_company_json()
    )

    filings_data, filings_path = (
        load_filings(
            company_json_path
        )
    )

    company_name = (
        company["company_name"]
    )

    corp_code = (
        company["corp_code"]
    )

    filings = (
        filings_data["filings"]
    )


    print(
        f"Company   : {company_name}"
    )

    print(
        f"Corp Code : {corp_code}"
    )

    print(
        f"Filings   : {len(filings)}"
    )

    print(
        f"Source    : {filings_path}"
    )

    print()


    # -----------------------------------------------------
    # 기업별 raw 폴더
    # -----------------------------------------------------

    company_raw_dir = (
        RAW_ROOT
        / corp_code
    )

    company_raw_dir.mkdir(
        parents=True,
        exist_ok=True
    )


    # -----------------------------------------------------
    # 신고서 전 버전 반복
    # -----------------------------------------------------

    success_count = 0
    skip_count = 0
    fail_count = 0


    for index, filing in enumerate(
        filings,
        start=1
    ):

        rcept_no = (
            filing["rcept_no"]
        )

        rcept_dt = (
            filing["rcept_dt"]
        )

        report_nm = (
            filing["report_nm"]
        )

        extract_dir = (
            company_raw_dir
            / rcept_no
        )

        print(
            f"[{index}/{len(filings)}]"
        )

        print(
            f"Date   : {rcept_dt}"
        )

        print(
            f"Report : {report_nm}"
        )

        print(
            f"Rcept  : {rcept_no}"
        )


        # -------------------------------------------------
        # 이미 XML이 있으면 skip
        # -------------------------------------------------

        if already_downloaded(
            extract_dir
        ):

            print(
                "Status : SKIP (이미 다운로드됨)"
            )

            skip_count += 1

            print(
                "-" * 80
            )

            continue


        # -------------------------------------------------
        # 다운로드 + 압축 해제
        # -------------------------------------------------

        try:

            zip_path = download_filing(
                rcept_no=rcept_no,
                output_dir=company_raw_dir
            )

            extract_filing(
                zip_path=zip_path,
                extract_dir=extract_dir
            )

            xml_files = list(
                extract_dir.glob("*.xml")
            )

            if not xml_files:
                raise RuntimeError(
                    "압축 해제 후 XML 파일을 찾지 못했습니다."
                )

            print(
                f"Status : OK"
            )

            for xml_file in xml_files:

                print(
                    f"XML    : {xml_file}"
                )

            success_count += 1


        except Exception as e:

            print(
                f"Status : FAILED"
            )

            print(
                f"Error  : {e}"
            )

            fail_count += 1


        print(
            "-" * 80
        )


    # -----------------------------------------------------
    # 최종 요약
    # -----------------------------------------------------

    print()
    print("=" * 80)

    print("다운로드 결과")

    print(
        f"신규 성공 : {success_count}"
    )

    print(
        f"기존 파일 : {skip_count}"
    )

    print(
        f"실패      : {fail_count}"
    )

    print(
        f"저장 위치 : {company_raw_dir}"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()