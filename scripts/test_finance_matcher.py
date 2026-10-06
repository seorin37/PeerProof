from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


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
    match_finance_period,
)


# ============================================================
# JSON
# ============================================================

def load_json(
    path: Path,
):

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


# ============================================================
# 테스트용 후보 profile
# ============================================================

def make_fake_candidate(
    target_profile: dict,
    case: str,
) -> dict:

    candidate = copy.deepcopy(
        target_profile
    )

    candidate[
        "company"
    ] = (
        f"테스트후보기업_{case}"
    )

    # --------------------------------------------------------
    # CASE 1
    #
    # 대상:
    # 2022 FY
    # 2023 H1
    # 2023 Q3
    #
    # 후보:
    # 동일
    #
    # 기대:
    # 2023 Q3
    # --------------------------------------------------------

    if case == "Q3":

        return candidate

    # --------------------------------------------------------
    # CASE 2
    #
    # 후보는 Q3 없음
    #
    # 기대:
    # 2023 H1
    # --------------------------------------------------------

    if case == "H1":

        candidate[
            "periods"
        ].pop(
            "2023_Q3_YTD",
            None,
        )

        return candidate

    # --------------------------------------------------------
    # CASE 3
    #
    # 후보는 2022 FY만 있음
    #
    # 기대:
    # 2022 FY
    # --------------------------------------------------------

    if case == "FY":

        candidate[
            "periods"
        ] = {
            "2022_FY": (
                candidate[
                    "periods"
                ][
                    "2022_FY"
                ]
            )
        }

        return candidate

    # --------------------------------------------------------
    # CASE 4
    #
    # 아예 공통 기간 없음
    #
    # --------------------------------------------------------

    if case == "NONE":

        candidate[
            "periods"
        ] = {}

        return candidate

    raise ValueError(
        f"지원하지 않는 테스트 case: "
        f"{case}"
    )


# ============================================================
# 출력
# ============================================================

def print_result(
    result: dict,
):

    print()
    print(
        "=" * 70
    )

    print(
        f"{result['target_company']} "
        f"vs "
        f"{result['candidate_company']}"
    )

    print(
        "=" * 70
    )

    print(
        f"Finance 비교 가능: "
        f"{result['finance_comparable']}"
    )

    print(
        f"공통 기간       : "
        f"{result['common_periods']}"
    )

    print(
        f"선택 기간       : "
        f"{result['comparison_period']}"
    )

    if not result[
        "finance_comparable"
    ]:

        print(
            f"사유            : "
            f"{result['reason']}"
        )

        return

    print()
    print(
        "[대상기업]"
    )

    for key, value in (
        result[
            "target"
        ].items()
    ):

        print(
            f"{key:<24}: "
            f"{value}"
        )

    print()
    print(
        "[후보기업]"
    )

    for key, value in (
        result[
            "candidate"
        ].items()
    ):

        print(
            f"{key:<24}: "
            f"{value}"
        )


# ============================================================
# main
# ============================================================

def main():

    target_path = (
        ROOT_DIR
        / "data"
        / "processed"
        / "에이피알"
        / "finance"
        / "finance_profile.json"
    )

    if not target_path.exists():

        raise FileNotFoundError(
            f"finance_profile.json이 없습니다:\n"
            f"{target_path}"
        )

    target_profile = (
        load_json(
            target_path
        )
    )

    print()
    print(
        "=" * 70
    )

    print(
        "PEERPROOF / "
        "FINANCE PERIOD MATCHER TEST"
    )

    print(
        "=" * 70
    )

    # ========================================================
    # 4가지 테스트
    # ========================================================

    for case in [
        "Q3",
        "H1",
        "FY",
        "NONE",
    ]:

        candidate_profile = (
            make_fake_candidate(
                target_profile,
                case,
            )
        )

        result = (
            match_finance_period(
                target_profile,
                candidate_profile,
            )
        )

        print_result(
            result
        )


if __name__ == "__main__":
    main()