import json
from pathlib import Path

import yaml
from bs4 import BeautifulSoup


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
# 2. 탐색할 키워드
# =========================================================

KEYWORDS = [
    "사업의 내용",
    "사업의 개요",
    "주요 제품",
    "제품 및 서비스",
    "브랜드",
    "사업",
    "제품",

    "비교기업",
    "유사회사",
    "사업 유사성",
    "재무 유사성",
    "업종 관련성",

    "PER",
    "주가수익비율",
    "상대가치",

    "주당 평가가액",
    "평가가액",
    "할인율",
    "희망공모가액",
    "확정공모가액",
]


# =========================================================
# 3. 설정 파일 로드
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
# 4. 대상 기업 찾기
# =========================================================

def find_company():
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

def load_filings(company_json_path):
    """
    기업별 filings.json을 읽는다.
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
# 6. XML 경로 찾기
# =========================================================

def find_xml_path(corp_code, rcept_no):
    """
    data/raw/<corp_code>/<rcept_no>/
    에서 XML 파일을 찾는다.
    """

    filing_dir = (
        RAW_ROOT
        / corp_code
        / rcept_no
    )

    if not filing_dir.exists():
        return None

    exact_path = (
        filing_dir
        / f"{rcept_no}.xml"
    )

    if exact_path.exists():
        return exact_path

    xml_files = list(
        filing_dir.glob("*.xml")
    )

    if len(xml_files) == 0:
        return None

    if len(xml_files) == 1:
        return xml_files[0]

    # 여러 개면 가장 큰 XML 사용
    xml_files.sort(
        key=lambda path: path.stat().st_size,
        reverse=True
    )

    return xml_files[0]


# =========================================================
# 7. XML → 텍스트 변환
# =========================================================

def load_text(xml_path):
    """
    XML 문서를 검색 가능한 텍스트로 변환한다.
    """

    raw = xml_path.read_bytes()

    soup = BeautifulSoup(
        raw,
        "lxml-xml"
    )

    text = "\n".join(
        item.strip()
        for item in soup.stripped_strings
        if item.strip()
    )

    return text


# =========================================================
# 8. 키워드 문맥 추출
# =========================================================

def find_keyword_contexts(
    text,
    keyword,
    before=300,
    after=500,
    max_results=3
):
    """
    한 키워드가 등장한 위치 주변의 문맥을 최대 3개 반환한다.
    """

    results = []

    start_pos = 0

    while True:

        index = text.find(
            keyword,
            start_pos
        )

        if index == -1:
            break

        snippet_start = max(
            0,
            index - before
        )

        snippet_end = min(
            len(text),
            index
            + len(keyword)
            + after
        )

        snippet = text[
            snippet_start:snippet_end
        ].strip()

        results.append(
            snippet
        )

        if len(results) >= max_results:
            break

        start_pos = (
            index
            + len(keyword)
        )

    return results


# =========================================================
# 9. 한 신고서 검사
# =========================================================

def inspect_filing(
    filing,
    corp_code
):
    """
    특정 신고서 XML 하나를 검사한다.
    """

    rcept_no = filing["rcept_no"]

    xml_path = find_xml_path(
        corp_code=corp_code,
        rcept_no=rcept_no
    )

    print()
    print("=" * 100)

    print(
        f"날짜      : {filing['rcept_dt']}"
    )

    print(
        f"문서명    : {filing['report_nm']}"
    )

    print(
        f"접수번호  : {rcept_no}"
    )


    if xml_path is None:

        print(
            "XML       : MISSING"
        )

        return


    text = load_text(
        xml_path
    )


    print(
        f"XML       : {xml_path}"
    )

    print(
        f"텍스트 길이: {len(text):,}"
    )

    print("=" * 100)


    for keyword in KEYWORDS:

        contexts = find_keyword_contexts(
            text=text,
            keyword=keyword
        )

        print()
        print("-" * 80)

        print(
            f"[검색어] {keyword}"
        )

        if not contexts:

            print(
                "검색 결과 없음"
            )

            continue


        print(
            f"발견 개수: {len(contexts)}"
            f" (최대 3개 출력)"
        )


        for index, snippet in enumerate(
            contexts,
            start=1
        ):

            print()
            print(
                f"--- 발견 {index} ---"
            )

            print(
                snippet
            )


# =========================================================
# 10. 요약 테이블 생성
# =========================================================

def build_keyword_summary(
    filings,
    corp_code
):
    """
    신고서별 키워드 존재 여부를 간단하게 요약한다.
    """

    summary = []

    for filing in filings:

        rcept_no = filing["rcept_no"]

        xml_path = find_xml_path(
            corp_code=corp_code,
            rcept_no=rcept_no
        )

        if xml_path is None:

            summary.append({
                "rcept_dt":
                    filing["rcept_dt"],

                "rcept_no":
                    rcept_no,

                "report_nm":
                    filing["report_nm"],

                "xml_status":
                    "missing",

                "keywords":
                    {},
            })

            continue


        text = load_text(
            xml_path
        )


        keyword_status = {}

        for keyword in KEYWORDS:

            keyword_status[
                keyword
            ] = (
                keyword in text
            )


        summary.append({

            "rcept_dt":
                filing["rcept_dt"],

            "rcept_no":
                rcept_no,

            "report_nm":
                filing["report_nm"],

            "xml_status":
                "ok",

            "keywords":
                keyword_status,
        })


    return summary


# =========================================================
# 11. 요약 출력
# =========================================================

def print_summary(summary):
    """
    어떤 신고서에 어떤 키워드가 있는지
    간단히 출력한다.
    """

    print()
    print()
    print("=" * 100)
    print("신고서 버전별 키워드 존재 여부 요약")
    print("=" * 100)


    for item in summary:

        print()
        print(
            f"{item['rcept_dt']}"
            f" | {item['report_nm']}"
            f" | {item['rcept_no']}"
        )

        print("-" * 100)


        if item["xml_status"] != "ok":

            print(
                "XML 파일 없음"
            )

            continue


        found = [
            keyword
            for keyword, exists
            in item["keywords"].items()
            if exists
        ]

        missing = [
            keyword
            for keyword, exists
            in item["keywords"].items()
            if not exists
        ]


        print(
            "FOUND   : "
            + (
                ", ".join(found)
                if found
                else "없음"
            )
        )

        print(
            "MISSING : "
            + (
                ", ".join(missing)
                if missing
                else "없음"
            )
        )


# =========================================================
# 12. 메인
# =========================================================

def main():

    print()
    print("=" * 100)
    print("PeerProof - IPO Filing Inspector")
    print("=" * 100)
    print()


    company_json_path, company = (
        find_company()
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
        f"Company : {company_name}"
    )

    print(
        f"Corp    : {corp_code}"
    )

    print(
        f"Filings : {len(filings)}"
    )

    print(
        f"Source  : {filings_path}"
    )


    # -----------------------------------------------------
    # 먼저 전체 버전 요약
    # -----------------------------------------------------

    summary = build_keyword_summary(
        filings=filings,
        corp_code=corp_code
    )

    print_summary(
        summary
    )


    # -----------------------------------------------------
    # 그 다음 버전별 상세 문맥 출력
    # -----------------------------------------------------

    for filing in filings:

        inspect_filing(
            filing=filing,
            corp_code=corp_code
        )


if __name__ == "__main__":
    main()