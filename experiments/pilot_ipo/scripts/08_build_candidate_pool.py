import io
import json
import os
import re
import time
import zipfile

from datetime import datetime, timedelta
from pathlib import Path

import requests
import yaml

from bs4 import BeautifulSoup
from dotenv import load_dotenv


# =========================================================
# 1. 기본 경로
# =========================================================

PROJECT_ROOT = Path("experiments/pilot_ipo")

TARGET_CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "target.yaml"
)

CANDIDATE_CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "candidate_pool.yaml"
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

CACHE_DIR = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "candidate_business"
)

HISTORICAL_OUTPUT_PATH = (
    PROCESSED_DIR
    / "historical_universe.json"
)

CANDIDATE_OUTPUT_PATH = (
    PROCESSED_DIR
    / "candidate_pool_stage2.json"
)


# =========================================================
# 2. API URL
# =========================================================

DART_CORP_CODE_URL = (
    "https://opendart.fss.or.kr/api/corpCode.xml"
)

DART_LIST_URL = (
    "https://opendart.fss.or.kr/api/list.json"
)

DART_DOCUMENT_URL = (
    "https://opendart.fss.or.kr/api/document.xml"
)

KRX_KOSPI_URL = (
    "https://data-dbg.krx.co.kr/"
    "svc/apis/sto/stk_isu_base_info"
)

KRX_KOSDAQ_URL = (
    "https://data-dbg.krx.co.kr/"
    "svc/apis/sto/ksq_isu_base_info"
)


# =========================================================
# 3. 사업 Section
# =========================================================

BUSINESS_START_HEADINGS = [
    "Ⅱ. 사업의 내용",
    "II. 사업의 내용",
    "사업의 내용",
    "사업의 개요",
    "주요 제품 및 서비스",
    "주요 제품 및 용역",
    "주요 제품",
    "매출 및 수주상황",
]

BUSINESS_END_HEADINGS = [
    "Ⅲ. 재무에 관한 사항",
    "III. 재무에 관한 사항",
    "재무에 관한 사항",
    "감사인의 감사의견",
    "이사회 등 회사의 기관",
    "주주에 관한 사항",
    "임원 및 직원 등에 관한 사항",
]


# =========================================================
# 4. YAML 읽기
# =========================================================

def load_yaml(path):

    if not path.exists():

        raise FileNotFoundError(
            f"설정 파일 없음: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return yaml.safe_load(f)


# =========================================================
# 5. 공통 Utility
# =========================================================

def normalize_stock_code(value):

    if value is None:
        return ""

    value = re.sub(
        r"[^0-9]",
        "",
        str(value)
    )

    if not value:
        return ""

    return value.zfill(6)


def normalize_date(value):

    value = re.sub(
        r"[^0-9]",
        "",
        str(value)
    )

    if len(value) != 8:

        raise ValueError(
            f"잘못된 날짜: {value}"
        )

    return value


def normalize_text(text):

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n+",
        "\n",
        text
    )

    return text.strip()


# =========================================================
# 6. DART corpCode 다운로드
# =========================================================

def fetch_dart_corp_codes(api_key):

    response = requests.get(
        DART_CORP_CODE_URL,
        params={
            "crtfc_key": api_key
        },
        timeout=30
    )

    response.raise_for_status()

    return response.content


# =========================================================
# 7. DART corpCode 파싱
# =========================================================

def parse_dart_corp_codes(zip_bytes):

    with zipfile.ZipFile(
        io.BytesIO(zip_bytes)
    ) as zf:

        names = zf.namelist()

        if not names:

            raise RuntimeError(
                "DART corpCode ZIP이 비어 있습니다."
            )

        xml_data = zf.read(
            names[0]
        )

    soup = BeautifulSoup(
        xml_data,
        "lxml-xml"
    )

    companies = []

    for item in soup.find_all("list"):

        stock_code = normalize_stock_code(
            item.stock_code.get_text(
                strip=True
            )
            if item.stock_code
            else ""
        )

        if not stock_code:
            continue

        corp_code = (
            item.corp_code.get_text(
                strip=True
            )
            if item.corp_code
            else ""
        )

        company_name = (
            item.corp_name.get_text(
                strip=True
            )
            if item.corp_name
            else ""
        )

        companies.append({

            "corp_code":
                corp_code,

            "company_name":
                company_name,

            "stock_code":
                stock_code,
        })

    return companies


# =========================================================
# 8. KRX API
# =========================================================

def fetch_krx_market(
    url,
    auth_key,
    bas_dd
):

    response = requests.get(
        url,
        headers={
            "AUTH_KEY": auth_key
        },
        params={
            "basDd": bas_dd
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    return data.get(
        "OutBlock_1",
        []
    )


# =========================================================
# 9. KRX 응답 정규화
# =========================================================

def normalize_krx_items(
    items,
    expected_market
):

    results = []

    for item in items:

        stock_code = normalize_stock_code(
            item.get(
                "ISU_SRT_CD"
            )
        )

        if not stock_code:
            continue

        security_group = (
            item.get(
                "SECUGRP_NM",
                ""
            )
        )

        stock_type = (
            item.get(
                "KIND_STKCERT_TP_NM",
                ""
            )
        )

        # 주권만 사용
        if (
            security_group
            and security_group != "주권"
        ):
            continue

        # 우선주 등 제외
        if (
            stock_type
            and "보통주" not in stock_type
        ):
            continue

        results.append({

            "stock_code":
                stock_code,

            "krx_company_name":
                item.get(
                    "ISU_ABBRV",
                    ""
                ),

            "market":
                item.get(
                    "MKT_TP_NM",
                    expected_market
                ),

            "listing_date":
                item.get(
                    "LIST_DD",
                    ""
                ),

            "listed_shares":
                item.get(
                    "LIST_SHRS",
                    ""
                ),
        })

    return results


# =========================================================
# 10. DART + KRX JOIN
# =========================================================

def join_dart_krx(
    dart_companies,
    krx_companies,
    target_name
):

    dart_map = {

        company["stock_code"]:
            company

        for company
        in dart_companies
    }

    joined = []

    not_found = 0

    target_excluded = 0

    for krx_company in krx_companies:

        stock_code = (
            krx_company[
                "stock_code"
            ]
        )

        dart_company = (
            dart_map.get(
                stock_code
            )
        )

        if not dart_company:

            not_found += 1

            continue

        if (
            dart_company[
                "company_name"
            ]
            == target_name
        ):

            target_excluded += 1

            continue

        joined.append({

            "corp_code":
                dart_company[
                    "corp_code"
                ],

            "stock_code":
                stock_code,

            "company_name":
                dart_company[
                    "company_name"
                ],

            "krx_company_name":
                krx_company[
                    "krx_company_name"
                ],

            "market":
                krx_company[
                    "market"
                ],

            "listing_date":
                krx_company[
                    "listing_date"
                ],

            "listed_shares":
                krx_company[
                    "listed_shares"
                ],
        })

    return joined, {

        "dart_not_found":
            not_found,

        "target_excluded":
            target_excluded,
    }


# =========================================================
# 11. 분석 시점 이전 최신 정기공시 찾기
# =========================================================

def find_latest_periodic_filing(
    dart_api_key,
    corp_code,
    analysis_date,
    lookback_days
):

    end_dt = datetime.strptime(
        analysis_date,
        "%Y%m%d"
    )

    begin_dt = (
        end_dt
        - timedelta(
            days=lookback_days
        )
    )

    response = requests.get(
        DART_LIST_URL,
        params={
            "crtfc_key":
                dart_api_key,

            "corp_code":
                corp_code,

            "bgn_de":
                begin_dt.strftime(
                    "%Y%m%d"
                ),

            "end_de":
                analysis_date,

            "pblntf_ty":
                "A",

            "page_count":
                100,
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if data.get("status") != "000":

        return None

    filings = data.get(
        "list",
        []
    )

    report_keywords = [
        "사업보고서",
        "반기보고서",
        "분기보고서",
    ]

    valid_reports = []

    for filing in filings:

        report_name = (
            filing.get(
                "report_nm",
                ""
            )
        )

        if not any(
            keyword in report_name
            for keyword
            in report_keywords
        ):
            continue

        valid_reports.append(
            filing
        )

    if not valid_reports:
        return None

    valid_reports.sort(
        key=lambda x: (
            x.get(
                "rcept_dt",
                ""
            ),
            x.get(
                "rcept_no",
                ""
            )
        ),
        reverse=True
    )

    return valid_reports[0]


# =========================================================
# 12. DART 원문 다운로드
# =========================================================

def fetch_dart_document(
    dart_api_key,
    rcept_no
):

    response = requests.get(
        DART_DOCUMENT_URL,
        params={
            "crtfc_key":
                dart_api_key,

            "rcept_no":
                rcept_no,
        },
        timeout=60
    )

    response.raise_for_status()

    content = response.content

    if not content.startswith(
        b"PK"
    ):

        raise RuntimeError(
            f"DART document ZIP 아님: {rcept_no}"
        )

    return content


# =========================================================
# 13. ZIP → 텍스트
# =========================================================

def extract_document_text(
    zip_bytes
):

    texts = []

    with zipfile.ZipFile(
        io.BytesIO(
            zip_bytes
        )
    ) as zf:

        for name in zf.namelist():

            lower_name = (
                name.lower()
            )

            if not (
                lower_name.endswith(
                    ".xml"
                )
                or lower_name.endswith(
                    ".html"
                )
                or lower_name.endswith(
                    ".htm"
                )
            ):

                continue

            raw = zf.read(
                name
            )

            try:

                soup = BeautifulSoup(
                    raw,
                    "lxml-xml"
                )

                text = "\n".join(
                    value.strip()

                    for value
                    in soup.stripped_strings

                    if value.strip()
                )

                if text:

                    texts.append(
                        text
                    )

            except Exception:

                continue

    return "\n".join(
        texts
    )


# =========================================================
# 14. 사업의 내용 영역 추출
# =========================================================

def extract_business_text(
    text
):

    if not text:
        return ""

    starts = []

    for heading in BUSINESS_START_HEADINGS:

        pos = text.find(
            heading
        )

        if pos != -1:

            starts.append(
                pos
            )

    if not starts:

        return ""

    start = min(
        starts
    )

    ends = []

    for heading in BUSINESS_END_HEADINGS:

        pos = text.find(
            heading,
            start + 1
        )

        if pos != -1:

            ends.append(
                pos
            )

    if ends:

        end = min(
            ends
        )

    else:

        end = min(
            len(text),
            start + 150000
        )

    return normalize_text(
        text[
            start:end
        ]
    )


# =========================================================
# 15. 개념 그룹 매칭
# =========================================================

def find_group_matches(
    text,
    groups
):

    lowered = text.lower()

    matched_groups = {}

    for group_name, keywords in groups.items():

        matched_keywords = []

        for keyword in keywords:

            if (
                keyword.lower()
                in lowered
            ):

                matched_keywords.append(
                    keyword
                )

        if matched_keywords:

            matched_groups[
                group_name
            ] = sorted(
                set(
                    matched_keywords
                )
            )

    return matched_groups


# =========================================================
# 16. 기업 Business 데이터 생성 / Cache
# =========================================================

def get_company_business_data(
    company,
    dart_api_key,
    analysis_date,
    config
):

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    cache_path = (
        CACHE_DIR
        / f"{company['corp_code']}.json"
    )


    # -----------------------------------------------------
    # Cache
    # -----------------------------------------------------

    if cache_path.exists():

        try:

            with open(
                cache_path,
                "r",
                encoding="utf-8"
            ) as f:

                cached = json.load(
                    f
                )

            if (
                cached.get(
                    "analysis_as_of"
                )
                == analysis_date
            ):

                return cached

        except Exception:

            pass


    dart_scan = config.get(
        "dart_scan",
        {}
    )

    lookback_days = int(
        dart_scan.get(
            "lookback_days",
            800
        )
    )


    # -----------------------------------------------------
    # 최신 정기공시
    # -----------------------------------------------------

    filing = find_latest_periodic_filing(

        dart_api_key=
            dart_api_key,

        corp_code=
            company[
                "corp_code"
            ],

        analysis_date=
            analysis_date,

        lookback_days=
            lookback_days,
    )


    if not filing:

        result = {

            "analysis_as_of":
                analysis_date,

            "company":
                company,

            "filing":
                None,

            "business_text":
                "",
        }

    else:

        document_zip = (
            fetch_dart_document(

                dart_api_key=
                    dart_api_key,

                rcept_no=
                    filing[
                        "rcept_no"
                    ],
            )
        )

        full_text = (
            extract_document_text(
                document_zip
            )
        )

        business_text = (
            extract_business_text(
                full_text
            )
        )

        result = {

            "analysis_as_of":
                analysis_date,

            "company":
                company,

            "filing": {

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
            },

            "business_text":
                business_text,
        }


    # -----------------------------------------------------
    # Cache 저장
    # -----------------------------------------------------

    with open(
        cache_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2
        )

    return result


# =========================================================
# 17. Business Candidate Filter
# =========================================================

def build_business_candidates(
    companies,
    dart_api_key,
    analysis_date,
    pool_config
):

    industry_groups = (
        pool_config.get(
            "industry_groups",
            {}
        )
    )

    business_groups = (
        pool_config.get(
            "business_groups",
            {}
        )
    )

    min_industry_groups = int(
        pool_config.get(
            "min_industry_groups",
            1
        )
    )

    min_business_groups = int(
        pool_config.get(
            "min_business_groups",
            2
        )
    )

    dart_scan = (
        pool_config.get(
            "dart_scan",
            {}
        )
    )

    request_delay = float(
        dart_scan.get(
            "request_delay_sec",
            0.15
        )
    )

    candidates = []

    stats = {

        "checked":
            0,

        "no_filing":
            0,

        "no_business_text":
            0,

        "industry_failed":
            0,

        "business_failed":
            0,

        "passed":
            0,
    }

    total = len(
        companies
    )


    for index, company in enumerate(
        companies,
        start=1
    ):

        try:

            data = (
                get_company_business_data(

                    company=
                        company,

                    dart_api_key=
                        dart_api_key,

                    analysis_date=
                        analysis_date,

                    config=
                        pool_config,
                )
            )

        except Exception as e:

            print(
                f"[WARN] "
                f"{company['company_name']} "
                f"처리 실패: {e}"
            )

            continue


        stats[
            "checked"
        ] += 1


        # -------------------------------------------------
        # 정기공시 없음
        # -------------------------------------------------

        if not data.get(
            "filing"
        ):

            stats[
                "no_filing"
            ] += 1

            continue


        business_text = (
            data.get(
                "business_text",
                ""
            )
        )


        if not business_text:

            stats[
                "no_business_text"
            ] += 1

            continue


        # -------------------------------------------------
        # 산업 개념 그룹
        # -------------------------------------------------

        industry_group_matches = (
            find_group_matches(

                text=
                    business_text,

                groups=
                    industry_groups,
            )
        )


        # -------------------------------------------------
        # 사업구조 개념 그룹
        # -------------------------------------------------

        business_group_matches = (
            find_group_matches(

                text=
                    business_text,

                groups=
                    business_groups,
            )
        )


        # -------------------------------------------------
        # 최소 조건
        # -------------------------------------------------

        if (
            len(
                industry_group_matches
            )
            < min_industry_groups
        ):

            stats[
                "industry_failed"
            ] += 1

            continue


        if (
            len(
                business_group_matches
            )
            < min_business_groups
        ):

            stats[
                "business_failed"
            ] += 1

            continue


        # -------------------------------------------------
        # Prefilter Score
        #
        # 최종 기업 유사도 점수가 아님.
        # 09 BGE-M3 이전 후보 우선순위 점수.
        #
        # 산업 그룹 1개 = 3점
        # 사업구조 그룹 1개 = 1점
        # -------------------------------------------------

        prefilter_score = (

            len(
                industry_group_matches
            )
            * 3

            +

            len(
                business_group_matches
            )
        )


        candidate = dict(
            company
        )

        candidate[
            "source_filing"
        ] = data[
            "filing"
        ]

        candidate[
            "industry_group_matches"
        ] = industry_group_matches

        candidate[
            "business_group_matches"
        ] = business_group_matches

        candidate[
            "prefilter_score"
        ] = prefilter_score

        candidates.append(
            candidate
        )

        stats[
            "passed"
        ] += 1


        # -------------------------------------------------
        # Progress
        # -------------------------------------------------

        if (
            index % 25 == 0
            or index == total
        ):

            print(
                f"[{index}/{total}] "
                f"검사 완료 | "
                f"후보 {len(candidates)}"
            )


        time.sleep(
            request_delay
        )


    # =====================================================
    # 후보 정렬
    # =====================================================

    candidates.sort(

        key=lambda x: (

            x[
                "prefilter_score"
            ],

            len(
                x[
                    "industry_group_matches"
                ]
            ),

            len(
                x[
                    "business_group_matches"
                ]
            ),
        ),

        reverse=True
    )

    return (
        candidates,
        stats
    )


# =========================================================
# 18. JSON 저장
# =========================================================

def save_json(
    path,
    data
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# 19. Main
# =========================================================

def main():

    print()
    print("=" * 100)
    print(
        "PeerProof - Candidate Pool Builder"
    )
    print("=" * 100)
    print()


    # =====================================================
    # .env
    # =====================================================

    load_dotenv(
        ".env"
    )


    dart_api_key = os.getenv(
        "DART_API_KEY"
    )

    krx_auth_key = os.getenv(
        "KRX_AUTH_KEY"
    )


    if not dart_api_key:

        raise RuntimeError(
            "DART_API_KEY 없음"
        )

    if not krx_auth_key:

        raise RuntimeError(
            "KRX_AUTH_KEY 없음"
        )


    # =====================================================
    # Config
    # =====================================================

    target_config = load_yaml(
        TARGET_CONFIG_PATH
    )

    candidate_config = load_yaml(
        CANDIDATE_CONFIG_PATH
    )

    target_name = (
        target_config[
            "target"
        ][
            "company_name"
        ]
    )

    analysis_as_of = (
        target_config[
            "target"
        ][
            "analysis_as_of"
        ]
    )

    analysis_date = (
        normalize_date(
            analysis_as_of
        )
    )

    pool_config = (
        candidate_config[
            "candidate_pool"
        ]
    )


    print(
        f"Target Company : {target_name}"
    )

    print(
        f"Analysis As Of : {analysis_as_of}"
    )

    print(
        f"KRX basDd      : {analysis_date}"
    )

    print()


    # =====================================================
    # STEP 1
    # DART stock_code Universe
    # =====================================================

    print(
        "[STEP 1] DART stock_code Universe"
    )

    print(
        "-" * 100
    )

    dart_zip = (
        fetch_dart_corp_codes(
            dart_api_key
        )
    )

    dart_companies = (
        parse_dart_corp_codes(
            dart_zip
        )
    )

    print(
        f"DART stock_code 보유 기업 : "
        f"{len(dart_companies)}"
    )

    print()


    # =====================================================
    # STEP 2
    # KRX Historical Snapshot
    # =====================================================

    print(
        "[STEP 2] KRX Historical Snapshot"
    )

    print(
        "-" * 100
    )

    kospi_raw = (
        fetch_krx_market(

            KRX_KOSPI_URL,

            krx_auth_key,

            analysis_date
        )
    )

    kosdaq_raw = (
        fetch_krx_market(

            KRX_KOSDAQ_URL,

            krx_auth_key,

            analysis_date
        )
    )

    kospi = (
        normalize_krx_items(

            kospi_raw,

            "KOSPI"
        )
    )

    kosdaq = (
        normalize_krx_items(

            kosdaq_raw,

            "KOSDAQ"
        )
    )

    krx_companies = (
        kospi
        + kosdaq
    )


    print(
        f"KOSPI API 응답       : "
        f"{len(kospi_raw)}"
    )

    print(
        f"KOSDAQ API 응답      : "
        f"{len(kosdaq_raw)}"
    )

    print(
        f"보통주 중심 Universe : "
        f"{len(krx_companies)}"
    )

    print()


    # =====================================================
    # STEP 3
    # DART + KRX JOIN
    # =====================================================

    print(
        "[STEP 3] DART + KRX JOIN"
    )

    print(
        "-" * 100
    )

    (
        historical_universe,
        join_stats
    ) = join_dart_krx(

        dart_companies=
            dart_companies,

        krx_companies=
            krx_companies,

        target_name=
            target_name,
    )


    print(
        f"DART 매핑 실패       : "
        f"{join_stats['dart_not_found']}"
    )

    print(
        f"Target 제외          : "
        f"{join_stats['target_excluded']}"
    )

    print(
        f"Historical Universe  : "
        f"{len(historical_universe)}"
    )

    print()


    # -----------------------------------------------------
    # Historical Universe 저장
    # -----------------------------------------------------

    save_json(

        HISTORICAL_OUTPUT_PATH,

        {
            "target_company":
                target_name,

            "analysis_as_of":
                analysis_as_of,

            "count":
                len(
                    historical_universe
                ),

            "companies":
                historical_universe,
        }
    )


    # =====================================================
    # STEP 4
    # DART Business Content Filter
    # =====================================================

    print(
        "[STEP 4] DART Business Content Filter"
    )

    print(
        "-" * 100
    )

    print(
        "각 기업의 분석시점 이전 "
        "최신 정기공시를 검사합니다."
    )

    print(
        "이미 검사한 기업은 cache를 사용합니다."
    )

    print()


    (
        business_candidates,
        filter_stats
    ) = build_business_candidates(

        companies=
            historical_universe,

        dart_api_key=
            dart_api_key,

        analysis_date=
            analysis_date,

        pool_config=
            pool_config,
    )


    # =====================================================
    # 후보 개수 제한
    # =====================================================

    max_candidates = int(
        pool_config.get(
            "max_candidates",
            50
        )
    )

    final_candidates = (
        business_candidates[
            :max_candidates
        ]
    )


    # =====================================================
    # 통계
    # =====================================================

    print()

    print(
        "Business Filter Stats"
    )

    print(
        "-" * 100
    )

    print(
        f"검사 기업       : "
        f"{filter_stats['checked']}"
    )

    print(
        f"정기공시 없음   : "
        f"{filter_stats['no_filing']}"
    )

    print(
        f"사업내용 없음   : "
        f"{filter_stats['no_business_text']}"
    )

    print(
        f"산업조건 탈락   : "
        f"{filter_stats['industry_failed']}"
    )

    print(
        f"사업조건 탈락   : "
        f"{filter_stats['business_failed']}"
    )

    print(
        f"조건 통과       : "
        f"{filter_stats['passed']}"
    )

    print(
        f"최종 저장 후보  : "
        f"{len(final_candidates)}"
    )

    print()


    # =====================================================
    # Candidate Preview
    # =====================================================

    print(
        "Candidate Pool Preview"
    )

    print(
        "-" * 100
    )

    for index, company in enumerate(
        final_candidates,
        start=1
    ):

        print(
            f"[{index}] "
            f"{company['company_name']} "
            f"({company['stock_code']})"
        )

        print(
            f"시장: "
            f"{company['market']}"
        )

        print(
            "Industry Groups: "
            f"{list(company['industry_group_matches'].keys())}"
        )

        print(
            "Industry Keywords: "
            f"{company['industry_group_matches']}"
        )

        print(
            "Business Groups: "
            f"{list(company['business_group_matches'].keys())}"
        )

        print(
            "Business Keywords: "
            f"{company['business_group_matches']}"
        )

        print(
            f"Prefilter Score: "
            f"{company['prefilter_score']}"
        )

        filing = (
            company[
                "source_filing"
            ]
        )

        print(
            f"공시: "
            f"{filing['rcept_dt']} / "
            f"{filing['report_nm']}"
        )

        print()


    # =====================================================
    # Candidate Pool 저장
    # =====================================================

    save_json(

        CANDIDATE_OUTPUT_PATH,

        {
            "target_company":
                target_name,

            "analysis_as_of":
                analysis_as_of,

            "pipeline": [

                "DART stock_code universe",

                "KRX historical snapshot",

                "DART + KRX join",

                "DART business content filter",

                "concept-group prefilter",

                "size filter - pending",

                "BGE-M3 similarity - pending",

                "language network similarity - pending",

                "late fusion - pending",
            ],

            "filter_config": {

                "industry_groups":
                    pool_config.get(
                        "industry_groups",
                        {}
                    ),

                "business_groups":
                    pool_config.get(
                        "business_groups",
                        {}
                    ),

                "min_industry_groups":
                    pool_config.get(
                        "min_industry_groups",
                        1
                    ),

                "min_business_groups":
                    pool_config.get(
                        "min_business_groups",
                        2
                    ),

                "max_candidates":
                    max_candidates,
            },

            "stats": {

                "dart_stock_universe":
                    len(
                        dart_companies
                    ),

                "historical_universe":
                    len(
                        historical_universe
                    ),

                "business_filter":
                    filter_stats,

                "all_passed_candidates":
                    len(
                        business_candidates
                    ),

                "saved_candidate_count":
                    len(
                        final_candidates
                    ),
            },

            "companies":
                final_candidates,
        }
    )


    # =====================================================
    # 완료 출력
    # =====================================================

    print(
        "=" * 100
    )

    print(
        f"Historical Universe 저장: "
        f"{HISTORICAL_OUTPUT_PATH}"
    )

    print(
        f"Candidate Pool 저장     : "
        f"{CANDIDATE_OUTPUT_PATH}"
    )

    print(
        "=" * 100
    )


if __name__ == "__main__":
    main()