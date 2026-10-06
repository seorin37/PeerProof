from __future__ import annotations

import re
from typing import Any


# ============================================================
# 표준 재무항목 정의
# ============================================================

FINANCE_ACCOUNTS = {
    "revenue": {
        "statement": {"IS", "CIS"},
        "account_ids": [
            "ifrs-full_Revenue",
            "dart_Revenue",
        ],
        "account_names": [
            "매출액",
            "매출",
            "영업수익",
            "수익(매출액)",
            "수익",
        ],
    },

    "operating_income": {
        "statement": {"IS", "CIS"},
        "account_ids": [
            "dart_OperatingIncomeLoss",
        ],
        "account_names": [
            "영업이익",
            "영업이익(손실)",
            "영업손익",
        ],
    },

    "net_income": {
        "statement": {"IS", "CIS"},
        "account_ids": [
            "ifrs-full_ProfitLoss",
            "ifrs-full_ProfitLossAttributableToOwnersOfParent",
        ],
        "account_names": [
            "당기순이익",
            "당기순이익(손실)",
            "분기순이익",
            "반기순이익",
            "연결당기순이익",
        ],
    },

    "operating_cash_flow": {
        "statement": {"CF"},
        "account_ids": [
            "ifrs-full_CashFlowsFromUsedInOperatingActivities",
        ],
        "account_names": [
            "영업활동현금흐름",
            "영업활동으로인한현금흐름",
            "영업활동으로 인한 현금흐름",
        ],
    },

    "total_assets": {
        "statement": {"BS"},
        "account_ids": [
            "ifrs-full_Assets",
        ],
        "account_names": [
            "자산총계",
            "자산총액",
        ],
    },

    "total_liabilities": {
        "statement": {"BS"},
        "account_ids": [
            "ifrs-full_Liabilities",
        ],
        "account_names": [
            "부채총계",
            "부채총액",
        ],
    },

    "total_equity": {
        "statement": {"BS"},
        "account_ids": [
            "ifrs-full_Equity",
        ],
        "account_names": [
            "자본총계",
            "자본총액",
        ],
    },
}


# ============================================================
# 숫자 변환
# ============================================================

def parse_amount(
    value: Any,
) -> int | float | None:

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    if text in {
        "-",
        "N/A",
        "null",
        "None",
    }:
        return None

    # 쉼표 제거
    text = text.replace(",", "")

    # 괄호형 음수
    # (1234) -> -1234
    if (
        text.startswith("(")
        and text.endswith(")")
    ):
        text = (
            "-"
            + text[1:-1]
        )

    try:
        number = float(text)

    except ValueError:
        return None

    if number.is_integer():
        return int(number)

    return number


# ============================================================
# 계정명 normalization
# ============================================================

def normalize_text(
    value: str | None,
) -> str:

    if not value:
        return ""

    value = value.lower()

    value = re.sub(
        r"\s+",
        "",
        value,
    )

    value = value.replace(
        "ㆍ",
        "",
    )

    value = value.replace(
        "·",
        "",
    )

    return value


# ============================================================
# 기간 유형
# ============================================================

def determine_period_type(
    dart_report_type: str,
) -> str:

    mapping = {
        "annual": "FY",
        "semiannual": "H1_YTD",
        "quarterly_1": "Q1_YTD",
        "quarterly_3": "Q3_YTD",
    }

    if dart_report_type not in mapping:
        raise ValueError(
            f"지원하지 않는 보고서 유형: "
            f"{dart_report_type}"
        )

    return mapping[
        dart_report_type
    ]


# ============================================================
# 재무제표 구분
# ============================================================

def get_statement_div(
    row: dict[str, Any],
) -> str:

    return str(
        row.get(
            "sj_div",
            "",
        )
    ).upper()


# ============================================================
# 현재기간 금액 선택
# ============================================================

def get_current_amount(
    row: dict[str, Any],
    period_type: str,
) -> tuple[
    int | float | None,
    str | None,
]:
    """
    반환:
        (금액, 사용한 DART 필드)

    BS:
        항상 thstrm_amount

    연간 IS/CIS/CF:
        thstrm_amount

    반기/분기 IS/CIS/CF:
        누적값 thstrm_add_amount 우선
    """

    sj_div = get_statement_div(
        row
    )

    # --------------------------------------------------------
    # 재무상태표
    # --------------------------------------------------------

    if sj_div == "BS":

        amount = parse_amount(
            row.get(
                "thstrm_amount"
            )
        )

        return (
            amount,
            "thstrm_amount",
        )

    # --------------------------------------------------------
    # 연간
    # --------------------------------------------------------

    if period_type == "FY":

        amount = parse_amount(
            row.get(
                "thstrm_amount"
            )
        )

        return (
            amount,
            "thstrm_amount",
        )

    # --------------------------------------------------------
    # 분기 / 반기
    #
    # 누적 금액 우선
    # --------------------------------------------------------

    cumulative = parse_amount(
        row.get(
            "thstrm_add_amount"
        )
    )

    if cumulative is not None:

        return (
            cumulative,
            "thstrm_add_amount",
        )

    # 없으면 thstrm_amount fallback

    amount = parse_amount(
        row.get(
            "thstrm_amount"
        )
    )

    return (
        amount,
        "thstrm_amount",
    )


# ============================================================
# 전기 금액
# ============================================================

def get_previous_amount(
    row: dict[str, Any],
    period_type: str,
) -> tuple[
    int | float | None,
    str | None,
]:

    sj_div = get_statement_div(
        row
    )

    if sj_div == "BS":

        amount = parse_amount(
            row.get(
                "frmtrm_amount"
            )
        )

        return (
            amount,
            "frmtrm_amount",
        )

    if period_type == "FY":

        amount = parse_amount(
            row.get(
                "frmtrm_amount"
            )
        )

        return (
            amount,
            "frmtrm_amount",
        )

    cumulative = parse_amount(
        row.get(
            "frmtrm_add_amount"
        )
    )

    if cumulative is not None:

        return (
            cumulative,
            "frmtrm_add_amount",
        )

    amount = parse_amount(
        row.get(
            "frmtrm_amount"
        )
    )

    return (
        amount,
        "frmtrm_amount",
    )


# ============================================================
# 특정 계정 후보 점수
# ============================================================

def score_account_candidate(
    row: dict[str, Any],
    config: dict[str, Any],
) -> int:

    score = 0

    sj_div = get_statement_div(
        row
    )

    account_id = str(
        row.get(
            "account_id",
            "",
        )
    )

    account_nm = normalize_text(
        row.get(
            "account_nm"
        )
    )

    # --------------------------------------------------------
    # 재무제표 종류
    # --------------------------------------------------------

    if sj_div not in config[
        "statement"
    ]:
        return -1

    # --------------------------------------------------------
    # account_id 정확 일치
    # 가장 신뢰도가 높음
    # --------------------------------------------------------

    if account_id in config[
        "account_ids"
    ]:

        score += 100

    # --------------------------------------------------------
    # 계정명 정확 일치
    # --------------------------------------------------------

    normalized_names = [
        normalize_text(name)
        for name
        in config[
            "account_names"
        ]
    ]

    if account_nm in normalized_names:

        score += 50

    # --------------------------------------------------------
    # 계정명 부분 일치
    # --------------------------------------------------------

    else:

        for candidate_name in (
            normalized_names
        ):

            if (
                candidate_name
                and candidate_name
                in account_nm
            ):

                score += 20
                break

    # --------------------------------------------------------
    # account_detail
    #
    # 특정 부문/세부계정은 총계보다 우선순위를 낮춤
    # --------------------------------------------------------

    detail = normalize_text(
        row.get(
            "account_detail"
        )
    )

    if detail:
        score -= 3

    return score


# ============================================================
# 하나의 표준 계정 추출
# ============================================================

def extract_account(
    rows: list[dict[str, Any]],
    standard_name: str,
    period_type: str,
) -> dict[str, Any]:

    config = FINANCE_ACCOUNTS[
        standard_name
    ]

    candidates = []

    for row in rows:

        score = (
            score_account_candidate(
                row,
                config,
            )
        )

        if score <= 0:
            continue

        current_amount, current_field = (
            get_current_amount(
                row,
                period_type,
            )
        )

        if current_amount is None:
            continue

        previous_amount, previous_field = (
            get_previous_amount(
                row,
                period_type,
            )
        )

        candidates.append(
            {
                "score": score,

                "value": (
                    current_amount
                ),

                "previous_value": (
                    previous_amount
                ),

                "account_id": (
                    row.get(
                        "account_id"
                    )
                ),

                "account_nm": (
                    row.get(
                        "account_nm"
                    )
                ),

                "account_detail": (
                    row.get(
                        "account_detail"
                    )
                ),

                "statement_div": (
                    row.get(
                        "sj_div"
                    )
                ),

                "statement_name": (
                    row.get(
                        "sj_nm"
                    )
                ),

                "current_field": (
                    current_field
                ),

                "previous_field": (
                    previous_field
                ),

                "current_period_name": (
                    row.get(
                        "thstrm_nm"
                    )
                ),

                "previous_period_name": (
                    row.get(
                        "frmtrm_nm"
                    )
                ),

                "currency": (
                    row.get(
                        "currency"
                    )
                ),
            }
        )

    if not candidates:

        return {
            "value": None,
            "previous_value": None,
            "status": "not_found",
        }

    # 점수가 높은 후보 우선
    candidates.sort(
        key=lambda item: (
            item["score"]
        ),
        reverse=True,
    )

    best = candidates[0]

    best[
        "status"
    ] = "found"

    # 디버깅을 위해 후보 수 기록
    best[
        "candidate_count"
    ] = len(
        candidates
    )

    return best


# ============================================================
# 비율 계산
# ============================================================

def safe_ratio(
    numerator: int | float | None,
    denominator: int | float | None,
    multiply: float = 100.0,
) -> float | None:

    if (
        numerator is None
        or denominator is None
        or denominator == 0
    ):
        return None

    return round(
        (
            numerator
            / denominator
        )
        * multiply,
        4,
    )


# ============================================================
# 하나의 보고서 Profile 생성
# ============================================================

def extract_finance_period(
    raw_data: dict[str, Any],
) -> dict[str, Any]:

    business_year = int(
        raw_data[
            "business_year"
        ]
    )

    dart_report_type = (
        raw_data[
            "dart_report_type"
        ]
    )

    period_type = (
        determine_period_type(
            dart_report_type
        )
    )

    period_key = (
        f"{business_year}_"
        f"{period_type}"
    )

    rows = raw_data.get(
        "statements",
        [],
    )

    accounts = {}

    for standard_name in (
        FINANCE_ACCOUNTS
    ):

        accounts[
            standard_name
        ] = (
            extract_account(
                rows=rows,
                standard_name=(
                    standard_name
                ),
                period_type=(
                    period_type
                ),
            )
        )

    # ========================================================
    # 파생지표
    # ========================================================

    revenue = accounts[
        "revenue"
    ].get(
        "value"
    )

    operating_income = accounts[
        "operating_income"
    ].get(
        "value"
    )

    net_income = accounts[
        "net_income"
    ].get(
        "value"
    )

    assets = accounts[
        "total_assets"
    ].get(
        "value"
    )

    liabilities = accounts[
        "total_liabilities"
    ].get(
        "value"
    )

    equity = accounts[
        "total_equity"
    ].get(
        "value"
    )

    operating_margin = (
        safe_ratio(
            operating_income,
            revenue,
        )
    )

    net_margin = (
        safe_ratio(
            net_income,
            revenue,
        )
    )

    debt_ratio = (
        safe_ratio(
            liabilities,
            equity,
        )
    )

    liability_ratio = (
        safe_ratio(
            liabilities,
            assets,
        )
    )

    # ========================================================
    # 동일 보고서가 제공하는 전기값으로 성장률
    # ========================================================

    previous_revenue = accounts[
        "revenue"
    ].get(
        "previous_value"
    )

    revenue_growth = None

    if (
        revenue is not None
        and previous_revenue is not None
        and previous_revenue != 0
    ):

        revenue_growth = round(
            (
                (
                    revenue
                    - previous_revenue
                )
                / abs(
                    previous_revenue
                )
            )
            * 100,
            4,
        )

    return {
        "period_key": (
            period_key
        ),

        "business_year": (
            business_year
        ),

        "period_type": (
            period_type
        ),

        "dart_report_type": (
            dart_report_type
        ),

        "fs_div": (
            raw_data.get(
                "fs_div"
            )
        ),

        "accounts": (
            accounts
        ),

        "ratios": {
            "operating_margin": (
                operating_margin
            ),

            "net_margin": (
                net_margin
            ),

            "debt_ratio": (
                debt_ratio
            ),

            "liability_ratio": (
                liability_ratio
            ),

            "revenue_growth_yoy": (
                revenue_growth
            ),
        },
    }