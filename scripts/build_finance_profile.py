from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


# ============================================================
# 프로젝트 경로
# ============================================================

ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)

SRC_DIR = (
    ROOT_DIR
    / "src"
)

sys.path.insert(
    0,
    str(SRC_DIR),
)


from peerproof.finance import (
    extract_finance_period,
)


PROCESSED_ROOT = (
    ROOT_DIR
    / "data"
    / "processed"
)


# ============================================================
# JSON
# ============================================================

def load_json(
    path: Path,
) -> dict[str, Any]:

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


def save_json(
    path: Path,
    data: Any,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# 최신 기간 정렬
# ============================================================

PERIOD_PRIORITY = {
    "FY": 0,
    "Q1_YTD": 1,
    "H1_YTD": 2,
    "Q3_YTD": 3,
}


def period_sort_key(
    period: dict[str, Any],
) -> tuple[int, int]:

    return (
        int(
            period[
                "business_year"
            ]
        ),
        PERIOD_PRIORITY.get(
            period[
                "period_type"
            ],
            -1,
        ),
    )


# ============================================================
# 요약 출력
# ============================================================

def print_period_summary(
    period: dict[str, Any],
) -> None:

    print()
    print(
        "-" * 70
    )

    print(
        period[
            "period_key"
        ]
    )

    print(
        "-" * 70
    )

    accounts = period[
        "accounts"
    ]

    display_names = {
        "revenue": "매출액",
        "operating_income": "영업이익",
        "net_income": "당기순이익",
        "operating_cash_flow": "영업활동현금흐름",
        "total_assets": "자산총계",
        "total_liabilities": "부채총계",
        "total_equity": "자본총계",
    }

    for key, korean_name in (
        display_names.items()
    ):

        result = accounts[
            key
        ]

        value = result.get(
            "value"
        )

        account_nm = result.get(
            "account_nm"
        )

        print(
            f"{korean_name:<14}"
            f": {value}"
        )

        if value is not None:

            print(
                f"  ↳ DART 계정명: "
                f"{account_nm}"
            )

    print()

    ratios = period[
        "ratios"
    ]

    print(
        "영업이익률      : "
        f"{ratios['operating_margin']}"
    )

    print(
        "순이익률        : "
        f"{ratios['net_margin']}"
    )

    print(
        "부채비율        : "
        f"{ratios['debt_ratio']}"
    )

    print(
        "매출 YoY        : "
        f"{ratios['revenue_growth_yoy']}"
    )


# ============================================================
# main
# ============================================================

def main():

    print()
    print(
        "=" * 70
    )

    print(
        "PEERPROOF / "
        "FINANCE PROFILE BUILDER"
    )

    print(
        "=" * 70
    )

    company_name = input(
        "\n기업명을 입력하세요: "
    ).strip()

    if not company_name:

        raise ValueError(
            "기업명이 비어 있습니다."
        )

    # ========================================================
    # Finance raw 폴더
    # ========================================================

    finance_dir = (
        PROCESSED_ROOT
        / company_name
        / "finance"
    )

    raw_dir = (
        finance_dir
        / "raw"
    )

    if not raw_dir.exists():

        raise FileNotFoundError(
            f"Finance raw 폴더가 없습니다:\n"
            f"{raw_dir}"
        )

    raw_files = sorted(
        raw_dir.glob(
            "*.json"
        )
    )

    if not raw_files:

        raise FileNotFoundError(
            "Finance raw JSON 파일이 없습니다."
        )

    print()
    print(
        f"[1/3] Raw Finance 파일 "
        f"{len(raw_files)}개 발견"
    )

    # ========================================================
    # 각 기간 추출
    # ========================================================

    periods = []

    for path in raw_files:

        print(
            f"  - {path.name}"
        )

        raw_data = load_json(
            path
        )

        try:

            period = (
                extract_finance_period(
                    raw_data
                )
            )

            period[
                "source_file"
            ] = path.name

            periods.append(
                period
            )

        except Exception as error:

            print(
                f"    [WARNING] "
                f"처리 실패: {error}"
            )

    if not periods:

        raise RuntimeError(
            "추출된 Finance 기간이 없습니다."
        )

    # ========================================================
    # 시간순 정렬
    # ========================================================

    periods.sort(
        key=period_sort_key
    )

    print()
    print(
        "[2/3] 재무항목 표준화 완료"
    )

    for period in periods:

        print_period_summary(
            period
        )

    # ========================================================
    # 가장 최신 기간
    # ========================================================

    latest_period = (
        periods[-1]
    )

    # ========================================================
    # profile 생성
    # ========================================================

    profile = {
        "company": (
            company_name
        ),

        "period_count": (
            len(periods)
        ),

        "available_periods": [
            period[
                "period_key"
            ]
            for period
            in periods
        ],

        "latest_period": (
            latest_period[
                "period_key"
            ]
        ),

        "latest_period_type": (
            latest_period[
                "period_type"
            ]
        ),

        "periods": {
            period[
                "period_key"
            ]: period
            for period
            in periods
        },
    }

    # ========================================================
    # 저장
    # ========================================================

    output_path = (
        finance_dir
        / "finance_profile.json"
    )

    save_json(
        output_path,
        profile,
    )

    print()
    print(
        "[3/3] Finance Profile 저장"
    )

    print()
    print(
        "=" * 70
    )

    print(
        "FINANCE PROFILE 완료"
    )

    print(
        "=" * 70
    )

    print(
        f"사용 가능 기간: "
        f"{profile['available_periods']}"
    )

    print(
        f"최신 기간     : "
        f"{profile['latest_period']}"
    )

    print()

    print(
        "저장 위치:"
    )

    print(
        output_path
    )


if __name__ == "__main__":
    main()