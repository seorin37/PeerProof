import json
import re
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
# 2. 현재 단계에서 추출할 필드
# =========================================================

FIELDS = {

    "peer_selection": {
        "description": "비교기업 선정 기준 관련 정보",
        "keywords": [
            "비교기업 선정",
            "사업 유사성",
            "재무 유사성",
            "업종 관련성",
            "유사회사 선정",
        ],
    },

    "per_method": {
        "description": "PER 상대가치 평가 방식",
        "keywords": [
            "주가수익비율(PER)",
            "PER 상대가치",
            "유사회사의 PER",
        ],
    },

    "final_offer_price": {
        "description": "최종 확정 공모가액",
        "keywords": [
            "확정공모가액",
            "확정 공모가액",
        ],
    },
}


# =========================================================
# 3. 설정 파일 읽기
# =========================================================

def load_config():

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
# 4. 현재 대상 기업 찾기
# =========================================================

def find_company():

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
            f"'{target_name}'의 company.json을 찾지 못했습니다."
        )

    if len(matches) > 1:
        raise RuntimeError(
            f"'{target_name}'의 company.json이 여러 개입니다."
        )

    return matches[0]


# =========================================================
# 5. filings.json 읽기
# =========================================================

def load_filings(company_json_path):

    filings_path = (
        company_json_path.parent
        / "filings.json"
    )

    if not filings_path.exists():
        raise FileNotFoundError(
            f"filings.json을 찾을 수 없습니다: {filings_path}"
        )

    with open(
        filings_path,
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)

    return data


# =========================================================
# 6. XML 경로 찾기
# =========================================================

def find_xml_path(
    corp_code,
    rcept_no
):

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

    if not xml_files:
        return None

    xml_files.sort(
        key=lambda path: path.stat().st_size,
        reverse=True
    )

    return xml_files[0]


# =========================================================
# 7. XML → 텍스트
# =========================================================

def load_text(
    corp_code,
    rcept_no
):

    xml_path = find_xml_path(
        corp_code=corp_code,
        rcept_no=rcept_no
    )

    if xml_path is None:
        return None

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
# 8. 키워드 전체 위치 찾기
# =========================================================

def find_all_occurrences(
    text,
    keyword
):

    positions = []

    start = 0

    while True:

        index = text.find(
            keyword,
            start
        )

        if index == -1:
            break

        positions.append(
            index
        )

        start = (
            index
            + len(keyword)
        )

    return positions


# =========================================================
# 9. 주변 문맥 추출
# =========================================================

def extract_context(
    text,
    position,
    keyword,
    before=500,
    after=1500
):

    start = max(
        0,
        position - before
    )

    end = min(
        len(text),
        position
        + len(keyword)
        + after
    )

    return text[
        start:end
    ].strip()


# =========================================================
# 10. peer_selection 유효성 검사
# =========================================================

def validate_peer_selection(
    snippet
):
    """
    비교기업 선정과 관련된 실제 설명인지 확인한다.

    단순히 '비교기업'이라는 단어만 등장하는 것은 제외하고,
    선정기준 관련 표현이 함께 존재해야 한다.
    """

    required_terms = [
        "사업 유사성",
        "재무 유사성",
        "업종 관련성",
        "일반사항",
        "선정",
    ]

    matched = [
        term
        for term in required_terms
        if term in snippet
    ]

    # 선정 기준 관련 표현이 최소 2개 이상 있어야 유효
    return len(matched) >= 2


# =========================================================
# 11. PER 방식 유효성 검사
# =========================================================

def validate_per_method(
    snippet
):
    """
    단순 PER 단어가 아니라
    실제 가치평가 방법 설명인지 확인한다.
    """

    has_per = (
        "PER" in snippet
        or "주가수익비율" in snippet
    )

    has_valuation_context = any(
        term in snippet
        for term in [
            "비교가치",
            "상대가치",
            "공모가",
            "유사회사",
            "평가",
        ]
    )

    return (
        has_per
        and has_valuation_context
    )


# =========================================================
# 12. 확정공모가 유효성 검사
# =========================================================

def validate_final_offer_price(
    snippet
):
    """
    '확정공모가액'이라는 단어만 있다고
    실제 확정된 것으로 보지 않는다.

    실제 숫자 + 확정 문맥이 같이 있어야 한다.
    """

    # 예:
    # 확정공모가액 250,000원
    price_pattern = re.compile(
        r"(?:확정공모가액|확정\s*공모가액)"
        r".{0,100}?"
        r"([0-9]{1,3}(?:,[0-9]{3})+)\s*원",
        re.DOTALL
    )

    match = price_pattern.search(
        snippet
    )

    if not match:
        return False, None

    # "예정"만 있는 문맥은 제외
    future_terms = [
        "예정입니다",
        "예정이며",
        "결정할 예정",
        "최종 결정할 예정",
    ]

    # 숫자가 있고, 확정 표현이 있는지 확인
    confirmed_terms = [
        "확정되었습니다",
        "최종 결정하였습니다",
        "확정공모가액",
    ]

    has_confirmed = any(
        term in snippet
        for term in confirmed_terms
    )

    only_future = (
        any(
            term in snippet
            for term in future_terms
        )
        and not (
            "확정되었습니다" in snippet
            or "최종 결정하였습니다" in snippet
        )
    )

    if only_future:
        return False, None

    if not has_confirmed:
        return False, None

    return True, match.group(1)


# =========================================================
# 13. 필드별 검증
# =========================================================

def validate_field(
    field_name,
    snippet
):

    if field_name == "peer_selection":

        valid = validate_peer_selection(
            snippet
        )

        return valid, None


    if field_name == "per_method":

        valid = validate_per_method(
            snippet
        )

        return valid, "PER" if valid else None


    if field_name == "final_offer_price":

        return validate_final_offer_price(
            snippet
        )


    return False, None


# =========================================================
# 14. 한 신고서에서 유효 후보 찾기
# =========================================================

def find_valid_candidate(
    text,
    field_name,
    field_config
):

    for keyword in field_config["keywords"]:

        positions = find_all_occurrences(
            text=text,
            keyword=keyword
        )

        for position in positions:

            snippet = extract_context(
                text=text,
                position=position,
                keyword=keyword
            )

            valid, value = validate_field(
                field_name=field_name,
                snippet=snippet
            )

            if valid:

                return {
                    "matched_keyword":
                        keyword,

                    "value":
                        value,

                    "snippet":
                        snippet,
                }

    return None


# =========================================================
# 15. 최신 → 과거 fallback
# =========================================================

def resolve_field(
    field_name,
    field_config,
    filings,
    filing_texts
):

    checked_versions = []

    for filing in filings:

        rcept_no = (
            filing["rcept_no"]
        )

        checked_versions.append(
            rcept_no
        )

        text = filing_texts.get(
            rcept_no
        )

        if not text:
            continue

        candidate = find_valid_candidate(
            text=text,
            field_name=field_name,
            field_config=field_config
        )

        if candidate is None:
            continue

        return {

            "status":
                "found",

            "description":
                field_config["description"],

            "value":
                candidate["value"],

            "matched_keyword":
                candidate["matched_keyword"],

            "snippet":
                candidate["snippet"],

            "source": {
                "rcept_no":
                    filing["rcept_no"],

                "rcept_dt":
                    filing["rcept_dt"],

                "report_nm":
                    filing["report_nm"],
            },

            "checked_versions":
                checked_versions,
        }

    return {

        "status":
            "not_found",

        "description":
            field_config["description"],

        "value":
            None,

        "matched_keyword":
            None,

        "snippet":
            None,

        "source":
            None,

        "checked_versions":
            checked_versions,
    }


# =========================================================
# 16. 메인
# =========================================================

def main():

    print()
    print("=" * 100)
    print("PeerProof - Filing Version Resolver")
    print("=" * 100)
    print()


    company_json_path, company = (
        find_company()
    )


    filings_data = load_filings(
        company_json_path
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

    print()


    # -----------------------------------------------------
    # 신고서 전체 텍스트 로딩
    # -----------------------------------------------------

    filing_texts = {}

    print("신고서 로딩")
    print("-" * 100)


    for filing in filings:

        rcept_no = (
            filing["rcept_no"]
        )

        text = load_text(
            corp_code=corp_code,
            rcept_no=rcept_no
        )

        if text is None:

            print(
                f"[MISSING] {rcept_no}"
            )

            continue


        filing_texts[
            rcept_no
        ] = text


        print(
            f"[OK] "
            f"{filing['rcept_dt']} "
            f"| {rcept_no} "
            f"| {len(text):,} chars"
        )


    print()


    # -----------------------------------------------------
    # 필드 resolve
    # -----------------------------------------------------

    resolved_fields = {}

    print("필드별 최신 유효 정보")
    print("-" * 100)


    for field_name, field_config in FIELDS.items():

        result = resolve_field(
            field_name=field_name,
            field_config=field_config,
            filings=filings,
            filing_texts=filing_texts
        )


        resolved_fields[
            field_name
        ] = result


        if result["status"] == "found":

            source = result["source"]

            print(
                f"[FOUND] "
                f"{field_name}"
                f" → {source['rcept_dt']}"
                f" / {result['matched_keyword']}"
            )


            if result["value"] is not None:

                print(
                    f"        value = {result['value']}"
                )

        else:

            print(
                f"[NOT FOUND] {field_name}"
            )


    # -----------------------------------------------------
    # 결과 저장
    # -----------------------------------------------------

    output = {

        "company": {
            "company_name":
                company_name,

            "corp_code":
                corp_code,

            "stock_code":
                company.get(
                    "stock_code"
                ),
        },

        "analysis_as_of":
            filings_data["analysis_as_of"],

        "version_policy": (
            "신고서를 최신순으로 탐색하며, "
            "키워드 존재 여부뿐 아니라 필드별 유효성 검사를 통과한 "
            "가장 최신 신고서를 해당 필드의 출처로 채택한다."
        ),

        "resolved_fields":
            resolved_fields,
    }


    output_path = (
        company_json_path.parent
        / "resolved_fields.json"
    )


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


    print()
    print("=" * 100)

    print(
        f"저장 완료: {output_path}"
    )

    print("=" * 100)


if __name__ == "__main__":
    main()