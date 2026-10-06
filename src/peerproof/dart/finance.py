from __future__ import annotations

from typing import Any

from peerproof.dart.client import DartClient


class DartFinanceService:
    """
    DART 재무제표 API 서비스.

    사용 API:
    fnlttSinglAcntAll.json

    목적:
    기업의 재무제표 전체 계정과목을 가져온다.
    """

    ENDPOINT = "fnlttSinglAcntAll.json"

    # ========================================================
    # 보고서 코드
    # ========================================================

    REPORT_CODES = {
        "annual": "11011",
        "semiannual": "11012",
        "quarterly_1": "11013",
        "quarterly_3": "11014",
    }

    def __init__(
        self,
        client: DartClient,
    ):
        self.client = client

    # ========================================================
    # 보고서 코드 변환
    # ========================================================

    @classmethod
    def get_report_code(
        cls,
        report_type: str,
    ) -> str:

        if report_type not in cls.REPORT_CODES:
            raise ValueError(
                f"지원하지 않는 report_type입니다: {report_type}"
            )

        return cls.REPORT_CODES[
            report_type
        ]

    # ========================================================
    # 전체 재무제표 조회
    # ========================================================

    def get_financial_statements(
        self,
        corp_code: str,
        business_year: str | int,
        report_type: str,
        fs_div: str = "CFS",
    ) -> list[dict[str, Any]]:
        """
        fs_div:
        - CFS = 연결재무제표
        - OFS = 별도재무제표
        """

        report_code = (
            self.get_report_code(
                report_type
            )
        )

        params = {
            "corp_code": corp_code,
            "bsns_year": str(
                business_year
            ),
            "reprt_code": report_code,
            "fs_div": fs_div,
        }

        result = (
            self.client.get_json(
                self.ENDPOINT,
                params=params,
            )
        )

        if not result:
            return []

        if isinstance(
            result,
            dict,
        ):
            return result.get(
                "list",
                [],
            )

        return result