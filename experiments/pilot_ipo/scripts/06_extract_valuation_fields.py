import json
import re
from pathlib import Path

from bs4 import BeautifulSoup


# =========================================================
# 1. 기본 경로
# =========================================================

PROJECT_ROOT = Path("experiments/pilot_ipo")

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
# 2. JSON 읽기
# =========================================================

def load_json(path):

    if not path.exists():
        raise FileNotFoundError(
            f"파일을 찾을 수 없습니다: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


# =========================================================
# 3. 대상 기업 찾기
# =========================================================

def find_company_dir():

    candidates = []

    for company_dir in PROCESSED_ROOT.iterdir():

        if not company_dir.is_dir():
            continue

        company_json = (
            company_dir
            / "company.json"
        )

        resolved_json = (
            company_dir
            / "resolved_fields.json"
        )

        if (
            company_json.exists()
            and resolved_json.exists()
        ):
            candidates.append(
                company_dir
            )

    if len(candidates) == 0:
        raise FileNotFoundError(
            "분석 가능한 기업 폴더를 찾지 못했습니다."
        )

    if len(candidates) > 1:
        raise RuntimeError(
            "분석 대상 기업이 여러 개입니다. "
            "현재 pilot 단계에서는 하나의 기업만 사용합니다."
        )

    return candidates[0]


# =========================================================
# 4. XML 경로 찾기
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
# 5. XML → 텍스트
# =========================================================

def load_filing_text(
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

    return "\n".join(
        value.strip()
        for value in soup.stripped_strings
        if value.strip()
    )


# =========================================================
# 6. 숫자 변환
# =========================================================

def parse_int(value):

    if value is None:
        return None

    cleaned = re.sub(
        r"[^0-9]",
        "",
        str(value)
    )

    if not cleaned:
        return None

    return int(cleaned)


def parse_float(value):

    if value is None:
        return None

    cleaned = re.sub(
        r"[^0-9.]",
        "",
        str(value)
    )

    if not cleaned:
        return None

    return float(cleaned)


# =========================================================
# 7. 비교기업 선정 기준 추출
# =========================================================

def extract_peer_selection(
    resolved_fields
):

    field = resolved_fields.get(
        "peer_selection",
        {}
    )

    snippet = field.get(
        "snippet",
        ""
    )

    candidate_criteria = [
        "업종 관련성",
        "사업 유사성",
        "재무 유사성",
        "일반사항",
    ]

    criteria = [
        criterion
        for criterion in candidate_criteria
        if criterion in snippet
    ]

    return {
        "criteria": criteria,
        "source": field.get("source")
    }


# =========================================================
# 8. PER 평가 방식 추출
# =========================================================

def extract_per_method(
    resolved_fields
):

    field = resolved_fields.get(
        "per_method",
        {}
    )

    value = field.get(
        "value"
    )

    snippet = field.get(
        "snippet",
        ""
    )

    if value == "PER":
        method = "PER"

    elif (
        "PER" in snippet
        or "주가수익비율" in snippet
    ):
        method = "PER"

    else:
        method = None

    return {
        "method": method,
        "valuation_type": (
            "relative_valuation"
            if method
            else None
        ),
        "source": field.get("source")
    }


# =========================================================
# 9. 확정 공모가액 추출
# =========================================================

def extract_final_offer_price(
    resolved_fields
):

    field = resolved_fields.get(
        "final_offer_price",
        {}
    )

    value = parse_int(
        field.get("value")
    )

    return {
        "value": value,
        "currency": (
            "KRW"
            if value is not None
            else None
        ),
        "source": field.get("source")
    }


# =========================================================
# 10. 모든 신고서 텍스트 준비
# =========================================================

def load_all_filings(
    corp_code,
    filings
):

    filing_texts = []

    for filing in filings:

        text = load_filing_text(
            corp_code=corp_code,
            rcept_no=filing["rcept_no"]
        )

        if text is None:
            continue

        filing_texts.append({
            "rcept_no":
                filing["rcept_no"],

            "rcept_dt":
                filing["rcept_dt"],

            "report_nm":
                filing["report_nm"],

            "text":
                text,
        })

    return filing_texts


# =========================================================
# 11. 패턴 후보 찾기
# =========================================================

def find_pattern_in_filings(
    filing_texts,
    patterns
):

    for filing in filing_texts:

        text = filing["text"]

        for pattern_name, pattern in patterns:

            matches = list(
                re.finditer(
                    pattern,
                    text,
                    flags=re.DOTALL
                )
            )

            if not matches:
                continue

            for match in matches:

                start = max(
                    0,
                    match.start() - 300
                )

                end = min(
                    len(text),
                    match.end() + 500
                )

                context = text[
                    start:end
                ]

                # "정정 전" 문맥보다
                # 정정 후/현재 문맥을 우선하기 위한 단순 방어
                before_context = text[
                    max(0, match.start() - 200):
                    match.start()
                ]

                if (
                    "정정 전" in before_context
                    and "정정 후" not in before_context
                ):
                    continue

                return {
                    "match":
                        match,

                    "pattern":
                        pattern_name,

                    "context":
                        context,

                    "source": {
                        "rcept_no":
                            filing["rcept_no"],

                        "rcept_dt":
                            filing["rcept_dt"],

                        "report_nm":
                            filing["report_nm"],
                    },
                }

    return None


# =========================================================
# 12. 주당 평가가액
# =========================================================

def extract_valuation_price(
    filing_texts
):

    patterns = [

        (
            "valuation_price",
            r"주당\s*평가가액"
            r".{0,100}?"
            r"([0-9]{1,3}(?:,[0-9]{3})+)"
            r"\s*원"
        ),

        (
            "valuation_price_alt",
            r"평가가액"
            r".{0,100}?"
            r"([0-9]{1,3}(?:,[0-9]{3})+)"
            r"\s*원"
        ),
    ]

    result = find_pattern_in_filings(
        filing_texts,
        patterns
    )

    if result is None:
        return {
            "value": None,
            "currency": None,
            "source": None
        }

    value = parse_int(
        result["match"].group(1)
    )

    return {
        "value": value,
        "currency": "KRW",
        "source": result["source"],
        "evidence": result["context"],
    }


# =========================================================
# 13. 할인율
# =========================================================

def extract_discount_rate(
    filing_texts
):

    patterns = [

        (
            "discount_rate",
            r"평가액\s*대비\s*할인율"
            r".{0,100}?"
            r"([0-9]+(?:\.[0-9]+)?)\s*%"
            r"\s*[~∼\-]\s*"
            r"([0-9]+(?:\.[0-9]+)?)\s*%"
        ),
    ]

    result = find_pattern_in_filings(
        filing_texts,
        patterns
    )

    if result is None:
        return {
            "lower_price_discount": None,
            "upper_price_discount": None,
            "unit": "%",
            "source": None
        }

    first = parse_float(
        result["match"].group(1)
    )

    second = parse_float(
        result["match"].group(2)
    )

    return {
        "lower_price_discount": first,
        "upper_price_discount": second,
        "unit": "%",
        "source": result["source"],
        "evidence": result["context"],
    }


# =========================================================
# 14. 희망공모가 밴드
# =========================================================

def extract_offer_price_band(
    filing_texts
):

    patterns = [

        (
            "offer_price_band",
            r"(?:희망공모가액\s*밴드|희망공모가액)"
            r".{0,100}?"
            r"([0-9]{1,3}(?:,[0-9]{3})+)"
            r"\s*원?"
            r"\s*[~∼\-]\s*"
            r"([0-9]{1,3}(?:,[0-9]{3})+)"
            r"\s*원"
        ),
    ]

    result = find_pattern_in_filings(
        filing_texts,
        patterns
    )

    if result is None:
        return {
            "low": None,
            "high": None,
            "currency": None,
            "source": None
        }

    low = parse_int(
        result["match"].group(1)
    )

    high = parse_int(
        result["match"].group(2)
    )

    return {
        "low": low,
        "high": high,
        "currency": "KRW",
        "source": result["source"],
        "evidence": result["context"],
    }


# =========================================================
# 15. 메인
# =========================================================

def main():

    print()
    print("=" * 100)
    print("PeerProof - Valuation Field Extractor")
    print("=" * 100)
    print()

    company_dir = find_company_dir()

    company = load_json(
        company_dir
        / "company.json"
    )

    filings_data = load_json(
        company_dir
        / "filings.json"
    )

    resolved_data = load_json(
        company_dir
        / "resolved_fields.json"
    )

    company_name = company["company_name"]
    corp_code = company["corp_code"]

    resolved_fields = (
        resolved_data["resolved_fields"]
    )

    filings = filings_data["filings"]

    print(
        f"Company   : {company_name}"
    )

    print(
        f"Corp Code : {corp_code}"
    )

    print(
        f"As Of     : {company['analysis_as_of']}"
    )

    print()

    # -----------------------------------------------------
    # 신고서 전체 로딩
    # -----------------------------------------------------

    filing_texts = load_all_filings(
        corp_code=corp_code,
        filings=filings
    )

    print(
        f"Loaded filings: {len(filing_texts)}"
    )

    print()

    # -----------------------------------------------------
    # 구조화 값 추출
    # -----------------------------------------------------

    extracted = {

        "peer_selection":
            extract_peer_selection(
                resolved_fields
            ),

        "per_method":
            extract_per_method(
                resolved_fields
            ),

        "valuation_price":
            extract_valuation_price(
                filing_texts
            ),

        "discount_rate":
            extract_discount_rate(
                filing_texts
            ),

        "offer_price_band":
            extract_offer_price_band(
                filing_texts
            ),

        "final_offer_price":
            extract_final_offer_price(
                resolved_fields
            ),
    }

    # -----------------------------------------------------
    # 출력
    # -----------------------------------------------------

    print(
        "구조화 결과"
    )

    print("-" * 100)

    print(
        "Peer criteria :",
        extracted[
            "peer_selection"
        ][
            "criteria"
        ]
    )

    print(
        "PER method    :",
        extracted[
            "per_method"
        ][
            "method"
        ]
    )

    print(
        "Valuation     :",
        extracted[
            "valuation_price"
        ][
            "value"
        ]
    )

    print(
        "Discount      :",
        extracted[
            "discount_rate"
        ][
            "lower_price_discount"
        ],
        "~",
        extracted[
            "discount_rate"
        ][
            "upper_price_discount"
        ]
    )

    print(
        "Offer band    :",
        extracted[
            "offer_price_band"
        ][
            "low"
        ],
        "~",
        extracted[
            "offer_price_band"
        ][
            "high"
        ]
    )

    print(
        "Final price   :",
        extracted[
            "final_offer_price"
        ][
            "value"
        ]
    )

    # -----------------------------------------------------
    # JSON 저장
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
            company[
                "analysis_as_of"
            ],

        "valuation_fields":
            extracted,
    }

    output_path = (
        company_dir
        / "valuation_fields.json"
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
