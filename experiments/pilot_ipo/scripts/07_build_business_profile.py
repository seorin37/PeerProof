import json
import re

from pathlib import Path
from difflib import SequenceMatcher

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

KEYWORD_CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "profile_keywords.yaml"
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
# 2. Business Section 시작 후보
# =========================================================

BUSINESS_SECTION_STARTS = [
    "Ⅱ. 사업의 내용",
    "II. 사업의 내용",
    "사업의 내용",
    "1. 사업의 개요",
    "사업의 개요",
    "주요 제품 및 서비스",
    "주요 제품 및 용역",
    "주요 제품",
    "매출 및 수주상황",
]


# =========================================================
# 3. Business Section 종료 후보
# =========================================================

BUSINESS_SECTION_ENDS = [
    "Ⅲ. 재무에 관한 사항",
    "III. 재무에 관한 사항",
    "재무에 관한 사항",
    "Ⅳ. 감사인의 감사의견",
    "IV. 감사인의 감사의견",
    "감사인의 감사의견",
    "이사회 등 회사의 기관",
    "주주에 관한 사항",
    "임원 및 직원 등에 관한 사항",
]


# =========================================================
# 4. IPO / 공모 / 증권 노이즈
# =========================================================

IPO_EXCLUDE_TERMS = [
    "수요예측",
    "일반청약자",
    "기관투자자",
    "청약기일",
    "청약일",
    "공모주식",
    "상장공모",
    "희망공모가",
    "확정공모가",
    "공모가격",
    "공모가액",
    "공모방법",
    "공모금액",
    "인수회사",
    "대표주관회사",
    "공동주관회사",
    "인수단",
    "환매청구권",
    "상장예비심사",
    "유가증권시장 상장",
]


# =========================================================
# 5. 법률 / 투자 노이즈
# =========================================================

LEGAL_EXCLUDE_TERMS = [
    "자본시장과 금융투자업에 관한 법률",
    "증권 인수업무",
    "집합투자기구",
    "투자신탁",
    "고위험고수익",
    "조세특례제한법",
    "금융투자업자",
]


# =========================================================
# 6. 투자위험 노이즈
# =========================================================

RISK_EXCLUDE_TERMS = [
    "투자자께서는",
    "투자위험",
    "투자의사",
    "투자 의사",
    "유의하시기 바랍니다",
]


# =========================================================
# 7. 소송 / 분쟁 노이즈
# =========================================================

DISPUTE_EXCLUDE_TERMS = [
    "소송",
    "분쟁",
    "손해배상",
    "상표권 침해",
    "형사고소",
    "고소",
    "원고",
    "피고",
    "법원",
    "재심",
    "확정판결",
]


# =========================================================
# 8. 비교기업 문맥
# =========================================================

PEER_CONTEXT_TERMS = [
    "비교기업",
    "유사회사",
    "유사기업",
    "비교회사",
    "비교대상",
    "비교 대상",
    "사업유사성",
    "사업 유사성",
    "재무유사성",
    "재무 유사성",
    "업종 관련성",
    "선정하였습니다",
    "선정 기준",
    "선정기준",
    "제외하였습니다",
    "유사성이 적",
    "차이점이 있습니다",
    "사업구조의 차이",
]


# =========================================================
# 9. 산업 일반 문맥
# =========================================================

INDUSTRY_CONTEXT_TERMS = [
    "시장규모",
    "시장 규모",
    "시장 성장",
    "시장성장",
    "경쟁 심화",
    "진입 장벽",
    "산업 특성",
    "산업의 특성",
    "시장 전망",
    "산업 성장",
    "산업성장",
    "경쟁업체",
    "경쟁 환경",
]


# =========================================================
# 10. 설정 읽기
# =========================================================

def load_yaml(path):

    if not path.exists():
        raise FileNotFoundError(
            f"설정 파일을 찾을 수 없습니다: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:
        return yaml.safe_load(f)


def load_json(path):

    if not path.exists():
        raise FileNotFoundError(
            f"JSON 파일을 찾을 수 없습니다: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


# =========================================================
# 11. 키워드 설정 병합
# =========================================================

def load_profile_keywords():

    config = load_yaml(
        KEYWORD_CONFIG_PATH
    )

    common = config.get(
        "common",
        {}
    )

    domain = config.get(
        "domain",
        {}
    )

    categories = [
        "business",
        "product",
        "brand",
        "market",
    ]

    merged = {}

    for category in categories:

        common_keywords = common.get(
            category,
            []
        )

        domain_keywords = domain.get(
            category,
            []
        )

        merged[category] = list(
            dict.fromkeys(
                common_keywords
                + domain_keywords
            )
        )

    domain_name = domain.get(
        "name",
        "unknown"
    )

    return merged, domain_name


# =========================================================
# 12. 대상 기업 찾기
# =========================================================

def find_company():

    config = load_yaml(
        CONFIG_PATH
    )

    target_name = (
        config[
            "target"
        ][
            "company_name"
        ]
    )

    matches = []

    for company_json in (
        PROCESSED_ROOT.glob(
            "*/company.json"
        )
    ):

        company = load_json(
            company_json
        )

        if (
            company[
                "company_name"
            ]
            == target_name
        ):

            matches.append(
                (
                    company_json.parent,
                    company
                )
            )

    if len(matches) == 0:

        raise FileNotFoundError(
            f"기업을 찾을 수 없습니다: {target_name}"
        )

    if len(matches) > 1:

        raise RuntimeError(
            f"동일 기업 데이터가 여러 개입니다: {target_name}"
        )

    return matches[0]


# =========================================================
# 13. XML 경로
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
        filing_dir.glob(
            "*.xml"
        )
    )

    if not xml_files:
        return None

    xml_files.sort(
        key=lambda path:
            path.stat().st_size,
        reverse=True
    )

    return xml_files[0]


# =========================================================
# 14. XML → 텍스트
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

    return "\n".join(
        value.strip()
        for value
        in soup.stripped_strings
        if value.strip()
    )


# =========================================================
# 15. 문자열 정규화
# =========================================================

def normalize_text(text):

    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


# =========================================================
# 16. Business Section 추출
# =========================================================

def extract_business_regions(
    text
):

    regions = []

    starts = []

    for heading in (
        BUSINESS_SECTION_STARTS
    ):

        start = 0

        while True:

            position = text.find(
                heading,
                start
            )

            if position == -1:
                break

            starts.append(
                (
                    position,
                    heading
                )
            )

            start = (
                position
                + len(heading)
            )

    starts = sorted(
        set(starts),
        key=lambda x:
            x[0]
    )

    for (
        start_position,
        start_heading
    ) in starts:

        possible_ends = []

        for end_heading in (
            BUSINESS_SECTION_ENDS
        ):

            position = text.find(
                end_heading,
                (
                    start_position
                    + len(start_heading)
                )
            )

            if position != -1:

                possible_ends.append(
                    position
                )

        if possible_ends:

            end_position = min(
                possible_ends
            )

        else:

            end_position = min(
                len(text),
                start_position
                + 60000
            )

        region = text[
            start_position:
            end_position
        ].strip()

        if len(region) < 500:
            continue

        regions.append({

            "start_heading":
                start_heading,

            "text":
                region,
        })

    return regions


# =========================================================
# 17. 이미 추출된 Business Text → Region
#
# 후보 50개는 08에서 이미 business_text를 저장하므로
# XML Section 탐색을 다시 하지 않고 이 함수를 사용할 수 있음.
# =========================================================

def business_text_to_regions(
    business_text,
    start_heading="business_text"
):

    business_text = (
        business_text.strip()
        if business_text
        else ""
    )

    if not business_text:
        return []

    return [
        {
            "start_heading":
                start_heading,

            "text":
                business_text,
        }
    ]


# =========================================================
# 18. 문장 분리
# =========================================================

def split_sentences(text):

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    parts = re.split(
        r"(?<=[.!?。])\s+|\n+",
        text
    )

    sentences = []

    for part in parts:

        sentence = normalize_text(
            part
        )

        if len(sentence) < 30:
            continue

        if len(sentence) > 1200:
            continue

        sentences.append(
            sentence
        )

    return sentences


# =========================================================
# 19. Category 판정
# =========================================================

def classify_sentence(
    sentence,
    category_keywords
):

    categories = []

    for (
        category,
        keywords
    ) in (
        category_keywords.items()
    ):

        if any(
            keyword in sentence
            for keyword
            in keywords
        ):

            categories.append(
                category
            )

    return categories


# =========================================================
# 20. 노이즈 제거
# =========================================================

def should_exclude_noise(
    sentence
):

    exclusion_groups = [
        IPO_EXCLUDE_TERMS,
        LEGAL_EXCLUDE_TERMS,
        RISK_EXCLUDE_TERMS,
        DISPUTE_EXCLUDE_TERMS,
    ]

    for terms in exclusion_groups:

        if any(
            term in sentence
            for term in terms
        ):
            return True

    if (
        "정정 전" in sentence
        and len(sentence) < 400
    ):
        return True

    if (
        "정정사항" in sentence
        and len(sentence) < 400
    ):
        return True

    return False


# =========================================================
# 21. Target Anchor
# =========================================================

def has_target_anchor(
    sentence,
    company_name
):

    anchors = [
        "당사",
        "자사",
        company_name,
        f"㈜{company_name}",
        f"(주){company_name}",
    ]

    return any(
        anchor
        and anchor in sentence
        for anchor
        in anchors
    )


# =========================================================
# 22. 비교기업 문맥
# =========================================================

def is_peer_context(
    sentence,
    company_name
):

    if any(
        term in sentence
        for term in PEER_CONTEXT_TERMS
    ):
        return True

    # 기존 07 로직 유지
    if (
        "동사" in sentence
        and not has_target_anchor(
            sentence,
            company_name
        )
    ):
        return True

    return False


# =========================================================
# 23. 산업 일반 문맥
# =========================================================

def is_industry_context(
    sentence,
    company_name
):

    if has_target_anchor(
        sentence,
        company_name
    ):
        return False

    return any(
        term in sentence
        for term
        in INDUSTRY_CONTEXT_TERMS
    )


# =========================================================
# 24. Target Score
# =========================================================

def calculate_target_score(
    sentence,
    company_name
):

    score = 0

    if company_name in sentence:
        score += 4

    if (
        f"㈜{company_name}"
        in sentence
    ):
        score += 4

    if (
        f"(주){company_name}"
        in sentence
    ):
        score += 4

    if "당사" in sentence:
        score += 4

    if "자사" in sentence:
        score += 3

    if "회사는" in sentence:
        score += 1

    return score


# =========================================================
# 25. 관련도 점수
# =========================================================

def calculate_relevance_score(
    sentence,
    categories,
    company_name,
    category_keywords
):

    score = 0

    # Category 수
    score += (
        len(categories)
        * 2
    )

    # 실제 keyword 등장 수
    for keywords in (
        category_keywords.values()
    ):

        for term in keywords:

            if term in sentence:
                score += 1

    # 회사 Anchor
    score += (
        calculate_target_score(
            sentence=sentence,
            company_name=company_name
        )
    )

    # Category 조합 가점
    if (
        "business" in categories
        and "product" in categories
    ):
        score += 2

    if (
        "product" in categories
        and "brand" in categories
    ):
        score += 2

    if (
        "product" in categories
        and "market" in categories
    ):
        score += 2

    if (
        "brand" in categories
        and "market" in categories
    ):
        score += 1

    return score


# =========================================================
# 26. 유사 중복
# =========================================================

def is_near_duplicate(
    sentence,
    existing_sentences,
    threshold=0.93
):

    for existing in (
        existing_sentences
    ):

        ratio = SequenceMatcher(
            None,
            sentence,
            existing
        ).ratio()

        if ratio >= threshold:
            return True

    return False


# =========================================================
# 27. Evidence Collector 내부 엔진
#
# filing XML이든 후보 business_text든
# 결국 여기로 들어오도록 통일
# =========================================================

def collect_evidence_from_regions(
    regions,
    company_name,
    category_keywords,
    source,
    company_evidence=None,
    industry_context=None,
    company_seen=None,
    industry_seen=None,
    stats=None
):

    if company_evidence is None:
        company_evidence = []

    if industry_context is None:
        industry_context = []

    if company_seen is None:
        company_seen = []

    if industry_seen is None:
        industry_seen = []

    if stats is None:

        stats = {

            "filings_loaded":
                0,

            "business_regions":
                0,

            "sentences_checked":
                0,

            "noise_excluded":
                0,

            "peer_excluded":
                0,

            "no_category":
                0,

            "no_target_anchor":
                0,

            "company_duplicate":
                0,

            "industry_duplicate":
                0,
        }

    stats[
        "business_regions"
    ] += len(
        regions
    )

    for region in regions:

        sentences = (
            split_sentences(
                region[
                    "text"
                ]
            )
        )

        for sentence in sentences:

            stats[
                "sentences_checked"
            ] += 1

            # -----------------------------------------
            # 노이즈 제거
            # -----------------------------------------

            if should_exclude_noise(
                sentence
            ):

                stats[
                    "noise_excluded"
                ] += 1

                continue

            # -----------------------------------------
            # 비교기업 문맥 제거
            # -----------------------------------------

            if is_peer_context(
                sentence=sentence,
                company_name=company_name
            ):

                stats[
                    "peer_excluded"
                ] += 1

                continue

            # -----------------------------------------
            # Category
            # -----------------------------------------

            categories = (
                classify_sentence(
                    sentence=sentence,
                    category_keywords=(
                        category_keywords
                    )
                )
            )

            if not categories:

                stats[
                    "no_category"
                ] += 1

                continue

            normalized = (
                normalize_text(
                    sentence
                )
            )

            # -----------------------------------------
            # 산업 일반 문맥
            # -----------------------------------------

            if is_industry_context(
                normalized,
                company_name
            ):

                if is_near_duplicate(
                    normalized,
                    industry_seen
                ):

                    stats[
                        "industry_duplicate"
                    ] += 1

                    continue

                industry_seen.append(
                    normalized
                )

                industry_context.append({

                    "categories":
                        categories,

                    "text":
                        normalized,

                    "section": {

                        "start_heading":
                            region.get(
                                "start_heading",
                                "unknown"
                            ),
                    },

                    "source":
                        dict(source),
                })

                continue

            # -----------------------------------------
            # Company Anchor
            # -----------------------------------------

            if not has_target_anchor(
                normalized,
                company_name
            ):

                stats[
                    "no_target_anchor"
                ] += 1

                continue

            # -----------------------------------------
            # Relevance Score
            # -----------------------------------------

            score = (
                calculate_relevance_score(

                    sentence=
                        normalized,

                    categories=
                        categories,

                    company_name=
                        company_name,

                    category_keywords=
                        category_keywords
                )
            )

            # -----------------------------------------
            # 중복 제거
            # -----------------------------------------

            if is_near_duplicate(
                normalized,
                company_seen
            ):

                stats[
                    "company_duplicate"
                ] += 1

                continue

            company_seen.append(
                normalized
            )

            company_evidence.append({

                "categories":
                    categories,

                "relevance_score":
                    score,

                "text":
                    normalized,

                "section": {

                    "start_heading":
                        region.get(
                            "start_heading",
                            "unknown"
                        ),
                },

                "source":
                    dict(source),
            })

    return (
        company_evidence,
        industry_context,
        stats,
        company_seen,
        industry_seen,
    )


# =========================================================
# 28. 기존 Target IPO filing용 Evidence 수집
#
# 기존 07의 동작을 그대로 유지하기 위한 Wrapper
# =========================================================

def collect_evidence(
    corp_code,
    filings,
    company_name,
    category_keywords
):

    company_evidence = []
    industry_context = []

    company_seen = []
    industry_seen = []

    stats = {

        "filings_loaded":
            0,

        "business_regions":
            0,

        "sentences_checked":
            0,

        "noise_excluded":
            0,

        "peer_excluded":
            0,

        "no_category":
            0,

        "no_target_anchor":
            0,

        "company_duplicate":
            0,

        "industry_duplicate":
            0,
    }

    for filing in filings:

        text = load_text(
            corp_code=corp_code,
            rcept_no=filing[
                "rcept_no"
            ]
        )

        if text is None:
            continue

        stats[
            "filings_loaded"
        ] += 1

        regions = (
            extract_business_regions(
                text
            )
        )

        if not regions:
            continue

        source = {

            "rcept_no":
                filing.get(
                    "rcept_no"
                ),

            "rcept_dt":
                filing.get(
                    "rcept_dt"
                ),

            "report_nm":
                filing.get(
                    "report_nm"
                ),
        }

        (
            company_evidence,
            industry_context,
            stats,
            company_seen,
            industry_seen,
        ) = collect_evidence_from_regions(

            regions=
                regions,

            company_name=
                company_name,

            category_keywords=
                category_keywords,

            source=
                source,

            company_evidence=
                company_evidence,

            industry_context=
                industry_context,

            company_seen=
                company_seen,

            industry_seen=
                industry_seen,

            stats=
                stats,
        )

    return (
        company_evidence,
        industry_context,
        stats,
    )


# =========================================================
# 29. 후보기업 business_text용 Evidence 수집
#
# 09에서 이 함수를 그대로 사용할 예정
# =========================================================

def collect_evidence_from_business_text(
    business_text,
    company_name,
    category_keywords,
    source=None
):

    if source is None:

        source = {

            "rcept_no":
                None,

            "rcept_dt":
                None,

            "report_nm":
                None,
        }

    regions = (
        business_text_to_regions(
            business_text
        )
    )

    stats = {

        "filings_loaded":
            1 if regions else 0,

        "business_regions":
            0,

        "sentences_checked":
            0,

        "noise_excluded":
            0,

        "peer_excluded":
            0,

        "no_category":
            0,

        "no_target_anchor":
            0,

        "company_duplicate":
            0,

        "industry_duplicate":
            0,
    }

    (
        company_evidence,
        industry_context,
        stats,
        _,
        _,
    ) = collect_evidence_from_regions(

        regions=
            regions,

        company_name=
            company_name,

        category_keywords=
            category_keywords,

        source=
            source,

        stats=
            stats,
    )

    return (
        company_evidence,
        industry_context,
        stats,
    )


# =========================================================
# 30. Category별 정리
# =========================================================

def group_by_category(
    evidence
):

    grouped = {

        "business": [],
        "product": [],
        "brand": [],
        "market": [],
    }

    for item in evidence:

        for category in (
            item[
                "categories"
            ]
        ):

            if category not in grouped:
                continue

            grouped[
                category
            ].append(
                item
            )

    return grouped


# =========================================================
# 31. Core Evidence 선택
# =========================================================

def select_core_evidence(
    evidence,
    max_items=40
):

    ranked = sorted(

        evidence,

        key=lambda item:
            item[
                "relevance_score"
            ],

        reverse=True
    )

    selected = []

    categories = [
        "business",
        "product",
        "brand",
        "market",
    ]

    # 각 category에서 최대 5개 우선 확보
    for category in categories:

        added = 0

        for item in ranked:

            if (
                category
                not in item[
                    "categories"
                ]
            ):
                continue

            if item in selected:
                continue

            selected.append(
                item
            )

            added += 1

            if added >= 5:
                break

    # 남은 자리를 전체 relevance_score 순으로 채움
    for item in ranked:

        if (
            len(selected)
            >= max_items
        ):
            break

        if item in selected:
            continue

        selected.append(
            item
        )

    selected = sorted(

        selected,

        key=lambda item:
            item[
                "relevance_score"
            ],

        reverse=True
    )

    return selected[
        :max_items
    ]


# =========================================================
# 32. profile_text
# =========================================================

def build_profile_text(
    core_evidence
):

    return "\n".join(
        item[
            "text"
        ]
        for item
        in core_evidence
    )


# =========================================================
# 33. Business Profile 조립
#
# Target / Candidate 모두 같은 함수를 사용
# =========================================================

def assemble_business_profile(
    company,
    company_evidence,
    industry_context,
    stats,
    category_keywords,
    domain_name,
    max_core_items=40
):

    grouped = (
        group_by_category(
            company_evidence
        )
    )

    core_evidence = (
        select_core_evidence(

            evidence=
                company_evidence,

            max_items=
                max_core_items,
        )
    )

    profile_text = (
        build_profile_text(
            core_evidence
        )
    )

    output = {

        "company": {

            "company_name":
                company.get(
                    "company_name"
                ),

            "corp_code":
                company.get(
                    "corp_code"
                ),

            "stock_code":
                company.get(
                    "stock_code"
                ),
        },

        "analysis_as_of":
            company.get(
                "analysis_as_of"
            ),

        "profile_config": {

            "domain":
                domain_name,

            "keyword_config":
                str(
                    KEYWORD_CONFIG_PATH
                ),
        },

        "business_profile": {

            "extraction_stats":
                stats,

            "company_evidence_count":
                len(
                    company_evidence
                ),

            "industry_context_count":
                len(
                    industry_context
                ),

            "core_evidence_count":
                len(
                    core_evidence
                ),

            "category_counts": {

                category:
                    len(items)

                for (
                    category,
                    items
                ) in grouped.items()
            },

            "company_evidence":
                company_evidence,

            "industry_context":
                industry_context,

            "core_evidence":
                core_evidence,

            "profile_text":
                profile_text,
        }
    }

    return output


# =========================================================
# 34. Target IPO Filing → Business Profile
# =========================================================

def build_business_profile_from_filings(
    company,
    filings,
    category_keywords,
    domain_name,
    max_core_items=40
):

    (
        company_evidence,
        industry_context,
        stats
    ) = collect_evidence(

        corp_code=
            company[
                "corp_code"
            ],

        filings=
            filings,

        company_name=
            company[
                "company_name"
            ],

        category_keywords=
            category_keywords,
    )

    return assemble_business_profile(

        company=
            company,

        company_evidence=
            company_evidence,

        industry_context=
            industry_context,

        stats=
            stats,

        category_keywords=
            category_keywords,

        domain_name=
            domain_name,

        max_core_items=
            max_core_items,
    )


# =========================================================
# 35. Candidate Business Text → Business Profile
#
# 나중에 09가 사용할 핵심 함수
# =========================================================

def build_business_profile_from_text(
    company,
    business_text,
    source=None,
    category_keywords=None,
    domain_name=None,
    max_core_items=40
):

    if (
        category_keywords is None
        or domain_name is None
    ):

        (
            loaded_keywords,
            loaded_domain
        ) = load_profile_keywords()

        if category_keywords is None:
            category_keywords = (
                loaded_keywords
            )

        if domain_name is None:
            domain_name = (
                loaded_domain
            )

    (
        company_evidence,
        industry_context,
        stats
    ) = (
        collect_evidence_from_business_text(

            business_text=
                business_text,

            company_name=
                company[
                    "company_name"
                ],

            category_keywords=
                category_keywords,

            source=
                source,
        )
    )

    return assemble_business_profile(

        company=
            company,

        company_evidence=
            company_evidence,

        industry_context=
            industry_context,

        stats=
            stats,

        category_keywords=
            category_keywords,

        domain_name=
            domain_name,

        max_core_items=
            max_core_items,
    )


# =========================================================
# 36. Console 출력
# =========================================================

def print_profile_summary(
    output
):

    company = (
        output[
            "company"
        ]
    )

    profile = (
        output[
            "business_profile"
        ]
    )

    stats = (
        profile[
            "extraction_stats"
        ]
    )

    print(
        "Business Profile Extraction Stats"
    )

    print(
        "-" * 100
    )

    print(
        f"읽은 신고서          : "
        f"{stats['filings_loaded']}"
    )

    print(
        f"사업 section         : "
        f"{stats['business_regions']}"
    )

    print(
        f"검사한 문장          : "
        f"{stats['sentences_checked']}"
    )

    print(
        f"공모/법률/소송 제거 : "
        f"{stats['noise_excluded']}"
    )

    print(
        f"비교기업 문맥 제거   : "
        f"{stats['peer_excluded']}"
    )

    print(
        f"Target anchor 없음   : "
        f"{stats['no_target_anchor']}"
    )

    print(
        f"회사 유사중복 제거   : "
        f"{stats['company_duplicate']}"
    )

    print(
        f"산업 유사중복 제거   : "
        f"{stats['industry_duplicate']}"
    )

    print()

    print(
        "Business Profile Evidence"
    )

    print(
        "-" * 100
    )

    print(
        f"회사 자체 문장 : "
        f"{profile['company_evidence_count']}"
    )

    print(
        f"산업 일반 문장 : "
        f"{profile['industry_context_count']}"
    )

    for (
        category,
        count
    ) in (
        profile[
            "category_counts"
        ].items()
    ):

        print(
            f"{category:<10} : "
            f"{count}"
        )

    print(
        f"핵심 문장      : "
        f"{profile['core_evidence_count']}"
    )

    print()

    print(
        "핵심 Company Evidence 미리보기"
    )

    print(
        "-" * 100
    )

    for index, item in enumerate(
        profile[
            "core_evidence"
        ][:20],
        start=1
    ):

        print(
            f"[{index}] "
            f"score="
            f"{item['relevance_score']} "
            f"{item['categories']}"
        )

        print(
            item[
                "text"
            ][:500]
        )

        print(
            f"section: "
            f"{item['section']['start_heading']}"
        )

        print(
            f"출처: "
            f"{item['source'].get('rcept_dt')} "
            f"/ "
            f"{item['source'].get('rcept_no')}"
        )

        print()

    print(
        "Industry Context 미리보기"
    )

    print(
        "-" * 100
    )

    for index, item in enumerate(
        profile[
            "industry_context"
        ][:10],
        start=1
    ):

        print(
            f"[{index}] "
            f"{item['categories']}"
        )

        print(
            item[
                "text"
            ][:400]
        )

        print()


# =========================================================
# 37. 메인
#
# 현재는 기존과 동일하게 Target APR만 생성.
# 후보 50개는 다음 09에서
# build_business_profile_from_text()를 재사용.
# =========================================================

def main():

    print()

    print(
        "=" * 100
    )

    print(
        "PeerProof - Business Profile Builder"
    )

    print(
        "=" * 100
    )

    print()

    # -----------------------------------------------------
    # Target 기업
    # -----------------------------------------------------

    (
        company_dir,
        company
    ) = find_company()

    filings_data = load_json(
        company_dir
        / "filings.json"
    )

    (
        category_keywords,
        domain_name
    ) = load_profile_keywords()

    company_name = (
        company[
            "company_name"
        ]
    )

    corp_code = (
        company[
            "corp_code"
        ]
    )

    filings = (
        filings_data[
            "filings"
        ]
    )

    print(
        f"Company   : "
        f"{company_name}"
    )

    print(
        f"Corp Code : "
        f"{corp_code}"
    )

    print(
        f"As Of     : "
        f"{company['analysis_as_of']}"
    )

    print(
        f"Domain    : "
        f"{domain_name}"
    )

    print(
        f"Filings   : "
        f"{len(filings)}"
    )

    print()

    # -----------------------------------------------------
    # 동일 공통 Engine을 통해 Profile 생성
    # -----------------------------------------------------

    output = (
        build_business_profile_from_filings(

            company=
                company,

            filings=
                filings,

            category_keywords=
                category_keywords,

            domain_name=
                domain_name,

            max_core_items=
                40,
        )
    )

    # -----------------------------------------------------
    # Console
    # -----------------------------------------------------

    print_profile_summary(
        output
    )

    # -----------------------------------------------------
    # 저장
    # -----------------------------------------------------

    output_path = (
        company_dir
        / "business_profile.json"
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

    print(
        "=" * 100
    )

    print(
        f"저장 완료: "
        f"{output_path}"
    )

    print(
        "=" * 100
    )


if __name__ == "__main__":
    main()