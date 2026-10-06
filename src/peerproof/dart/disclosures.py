from datetime import datetime, timedelta

from .client import DartClient


class DisclosureService:
    """
    기업 공시 검색 및 정기보고서 선정.
    """

    REPORT_TYPES = {
        "사업보고서": "annual",
        "반기보고서": "semiannual",
        "분기보고서": "quarterly",
    }

    def __init__(self):
        self.client = DartClient()

    def get_disclosures(
        self,
        corp_code: str,
        start_date: str,
        end_date: str,
        page_count: int = 100,
    ):
        """
        특정 기업의 공시 목록 조회.

        여러 페이지가 존재하는 경우 모두 가져온다.
        """

        all_disclosures = []

        page_no = 1

        while True:

            params = {
                "corp_code": corp_code,
                "bgn_de": start_date,
                "end_de": end_date,
                "page_no": page_no,
                "page_count": page_count,
                "sort": "date",
                "sort_mth": "desc",
            }

            data = self.client.get_json(
                "list.json",
                params,
            )

            rows = data.get(
                "list",
                [],
            )

            if not rows:
                break

            all_disclosures.extend(
                rows
            )

            total_page = int(
                data.get(
                    "total_page",
                    1,
                )
            )

            if page_no >= total_page:
                break

            page_no += 1

        return all_disclosures

    @staticmethod
    def get_cutoff_date(
        ipo_date: str,
    ):
        """
        IPO 기준일 바로 전날 계산.

        예:
        20231222
        ->
        20231221
        """

        ipo_datetime = datetime.strptime(
            ipo_date,
            "%Y%m%d",
        )

        cutoff = (
            ipo_datetime
            - timedelta(days=1)
        )

        return cutoff.strftime(
            "%Y%m%d"
        )

    @classmethod
    def detect_report_type(
        cls,
        report_name: str,
    ):
        """
        보고서명을 정규화.

        [기재정정]사업보고서
        사업보고서
        모두 annual로 처리.
        """

        for keyword, report_type in (
            cls.REPORT_TYPES.items()
        ):

            if keyword in report_name:
                return report_type

        return None

    def get_periodic_reports(
        self,
        corp_code: str,
        start_date: str,
        ipo_date: str,
    ):
        """
        IPO 기준일 이전의 모든
        사업/반기/분기보고서 반환.
        """

        end_date = (
            self.get_cutoff_date(
                ipo_date
            )
        )

        disclosures = (
            self.get_disclosures(
                corp_code=corp_code,
                start_date=start_date,
                end_date=end_date,
            )
        )

        reports = []

        for disclosure in disclosures:

            report_name = (
                disclosure.get(
                    "report_nm",
                    "",
                )
            )

            report_type = (
                self.detect_report_type(
                    report_name
                )
            )

            if report_type is None:
                continue

            report = dict(
                disclosure
            )

            report[
                "report_type"
            ] = report_type

            reports.append(
                report
            )

        reports.sort(
            key=lambda x: x.get(
                "rcept_dt",
                "",
            ),
            reverse=True,
        )

        return reports

    def select_latest_reports(
        self,
        reports: list,
    ):
        """
        사업/반기/분기보고서 중
        각각 가장 최근 공시 하나만 선택.

        결과:
        {
            "annual": {...},
            "semiannual": {...},
            "quarterly": {...}
        }
        """

        selected = {
            "annual": None,
            "semiannual": None,
            "quarterly": None,
        }

        for report in reports:

            report_type = report[
                "report_type"
            ]

            if (
                selected[report_type]
                is None
            ):
                selected[
                    report_type
                ] = report

            if all(
                value is not None
                for value
                in selected.values()
            ):
                break

        return selected