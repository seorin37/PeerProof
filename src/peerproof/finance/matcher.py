from __future__ import annotations

from typing import Any


# ============================================================
# 기간 우선순위
# ============================================================

PERIOD_PRIORITY = {
    "FY": 0,
    "Q1_YTD": 1,
    "H1_YTD": 2,
    "Q3_YTD": 3,
}


# ============================================================
# period key 파싱
#
# 예:
# 2022_FY
# 2023_H1_YTD
# 2023_Q3_YTD
# ============================================================

def parse_period_key(
    period_key: str,
) -> tuple[int, str]:

    parts = period_key.split(
        "_",
        1,
    )

    if len(parts) != 2:
        raise ValueError(
            f"잘못된 period_key: {period_key}"
        )

    year_text = parts[0]
    period_type = parts[1]

    try:
        year = int(
            year_text
        )

    except ValueError as error:

        raise ValueError(
            f"period_key의 연도가 잘못되었습니다: "
            f"{period_key}"
        ) from error

    if period_type not in (
        PERIOD_PRIORITY
    ):

        raise ValueError(
            f"지원하지 않는 period_type: "
            f"{period_type}"
        )

    return (
        year,
        period_type,
    )


# ============================================================
# 기간 정렬 기준
# ============================================================

def period_sort_key(
    period_key: str,
) -> tuple[int, int]:

    year, period_type = (
        parse_period_key(
            period_key
        )
    )

    return (
        year,
        PERIOD_PRIORITY[
            period_type
        ],
    )


# ============================================================
# 기업의 사용 가능 기간 반환
# ============================================================

def get_available_periods(
    finance_profile: dict[str, Any],
) -> set[str]:

    periods = finance_profile.get(
        "periods",
        {},
    )

    if not isinstance(
        periods,
        dict,
    ):
        return set()

    return set(
        periods.keys()
    )


# ============================================================
# 공통 기간 찾기
# ============================================================

def find_common_periods(
    target_profile: dict[str, Any],
    candidate_profile: dict[str, Any],
) -> list[str]:

    target_periods = (
        get_available_periods(
            target_profile
        )
    )

    candidate_periods = (
        get_available_periods(
            candidate_profile
        )
    )

    common = (
        target_periods
        & candidate_periods
    )

    return sorted(
        common,
        key=period_sort_key,
    )


# ============================================================
# 가장 최신 공통기간
# ============================================================

def select_latest_common_period(
    target_profile: dict[str, Any],
    candidate_profile: dict[str, Any],
) -> str | None:

    common_periods = (
        find_common_periods(
            target_profile,
            candidate_profile,
        )
    )

    if not common_periods:
        return None

    return common_periods[-1]


# ============================================================
# 비교용 핵심지표 추출
# ============================================================

def extract_comparison_metrics(
    period_data: dict[str, Any],
) -> dict[str, Any]:

    accounts = period_data.get(
        "accounts",
        {},
    )

    ratios = period_data.get(
        "ratios",
        {},
    )

    def account_value(
        key: str,
    ) -> int | float | None:

        account = accounts.get(
            key,
            {},
        )

        return account.get(
            "value"
        )

    return {
        # ----------------------------------------------------
        # 규모
        # ----------------------------------------------------

        "revenue": (
            account_value(
                "revenue"
            )
        ),

        "total_assets": (
            account_value(
                "total_assets"
            )
        ),

        "total_equity": (
            account_value(
                "total_equity"
            )
        ),

        # ----------------------------------------------------
        # 수익성
        # ----------------------------------------------------

        "operating_income": (
            account_value(
                "operating_income"
            )
        ),

        "net_income": (
            account_value(
                "net_income"
            )
        ),

        "operating_margin": (
            ratios.get(
                "operating_margin"
            )
        ),

        "net_margin": (
            ratios.get(
                "net_margin"
            )
        ),

        # ----------------------------------------------------
        # 성장
        # ----------------------------------------------------

        "revenue_growth_yoy": (
            ratios.get(
                "revenue_growth_yoy"
            )
        ),

        # ----------------------------------------------------
        # 재무안정성
        # ----------------------------------------------------

        "total_liabilities": (
            account_value(
                "total_liabilities"
            )
        ),

        "debt_ratio": (
            ratios.get(
                "debt_ratio"
            )
        ),

        "liability_ratio": (
            ratios.get(
                "liability_ratio"
            )
        ),

        # ----------------------------------------------------
        # 현금흐름
        # ----------------------------------------------------

        "operating_cash_flow": (
            account_value(
                "operating_cash_flow"
            )
        ),
    }


# ============================================================
# 두 기업 Finance 1:1 매칭
# ============================================================

def match_finance_period(
    target_profile: dict[str, Any],
    candidate_profile: dict[str, Any],
) -> dict[str, Any]:

    target_company = (
        target_profile.get(
            "company",
            "UNKNOWN_TARGET",
        )
    )

    candidate_company = (
        candidate_profile.get(
            "company",
            "UNKNOWN_CANDIDATE",
        )
    )

    common_periods = (
        find_common_periods(
            target_profile,
            candidate_profile,
        )
    )

    # ========================================================
    # 공통기간 없음
    # ========================================================

    if not common_periods:

        return {
            "target_company": (
                target_company
            ),

            "candidate_company": (
                candidate_company
            ),

            "finance_comparable": False,

            "comparison_period": None,

            "common_periods": [],

            "reason": (
                "공통 재무기간이 없습니다."
            ),

            "target": None,

            "candidate": None,
        }

    # ========================================================
    # 가장 최신 공통기간 선택
    # ========================================================

    selected_period = (
        common_periods[-1]
    )

    target_period = (
        target_profile[
            "periods"
        ][
            selected_period
        ]
    )

    candidate_period = (
        candidate_profile[
            "periods"
        ][
            selected_period
        ]
    )

    # ========================================================
    # 비교 데이터
    # ========================================================

    target_metrics = (
        extract_comparison_metrics(
            target_period
        )
    )

    candidate_metrics = (
        extract_comparison_metrics(
            candidate_period
        )
    )

    return {
        "target_company": (
            target_company
        ),

        "candidate_company": (
            candidate_company
        ),

        "finance_comparable": True,

        "comparison_period": (
            selected_period
        ),

        "common_periods": (
            common_periods
        ),

        "target_period_type": (
            target_period.get(
                "period_type"
            )
        ),

        "candidate_period_type": (
            candidate_period.get(
                "period_type"
            )
        ),

        "target": (
            target_metrics
        ),

        "candidate": (
            candidate_metrics
        ),
    }