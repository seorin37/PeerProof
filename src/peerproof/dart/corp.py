import io
import zipfile
import xml.etree.ElementTree as ET

from .client import DartClient


class CorpCodeService:
    """
    DART 전체 기업 목록을 가져오고
    대상 기업의 corp_code를 찾는다.
    """

    def __init__(self):
        self.client = DartClient()

    def download_corp_codes(self):
        """
        DART의 전체 기업 고유번호 목록 다운로드.
        """

        response = self.client.get(
            "corpCode.xml"
        )

        content = response.content

        if content[:2] != b"PK":
            raise RuntimeError(
                "corpCode.xml 응답이 ZIP 형식이 아닙니다."
            )

        with zipfile.ZipFile(
            io.BytesIO(content)
        ) as zip_file:

            xml_files = [
                name
                for name in zip_file.namelist()
                if name.lower().endswith(".xml")
            ]

            if not xml_files:
                raise RuntimeError(
                    "기업 목록 ZIP 안에 XML 파일이 없습니다."
                )

            xml_data = zip_file.read(
                xml_files[0]
            )

        return xml_data

    def parse_corp_codes(
        self,
        xml_data: bytes,
    ):
        """
        XML -> Python list 변환.
        """

        root = ET.fromstring(
            xml_data
        )

        companies = []

        for item in root.findall("list"):

            company = {
                "corp_code": (
                    item.findtext("corp_code")
                    or ""
                ).strip(),

                "corp_name": (
                    item.findtext("corp_name")
                    or ""
                ).strip(),

                "corp_eng_name": (
                    item.findtext("corp_eng_name")
                    or ""
                ).strip(),

                "stock_code": (
                    item.findtext("stock_code")
                    or ""
                ).strip(),

                "modify_date": (
                    item.findtext("modify_date")
                    or ""
                ).strip(),
            }

            companies.append(
                company
            )

        return companies

    def get_all_companies(self):
        """
        전체 DART 기업 반환.
        """

        xml_data = (
            self.download_corp_codes()
        )

        return self.parse_corp_codes(
            xml_data
        )

    def search_company(
        self,
        keyword: str,
    ):
        """
        기업명을 포함 검색.

        예:
        에이피알

        →
        에이피알
        에이피알패션
        에이피알팩토리
        ...
        """

        keyword = (
            keyword
            .strip()
            .lower()
        )

        companies = (
            self.get_all_companies()
        )

        results = []

        for company in companies:

            corp_name = (
                company["corp_name"]
                .strip()
                .lower()
            )

            if keyword in corp_name:
                results.append(company)

        return results

    def find_exact_company(
        self,
        corp_name: str,
        stock_code: str | None = None,
    ):
        """
        정확한 회사명 + 종목코드로 기업 선택.

        상장사의 경우 stock_code 사용을 권장.
        """

        corp_name = corp_name.strip()

        if stock_code:
            stock_code = stock_code.strip()

        companies = (
            self.get_all_companies()
        )

        # 종목코드가 있다면 종목코드를 최우선으로 사용
        if stock_code:

            for company in companies:

                if (
                    company["stock_code"]
                    == stock_code
                ):
                    return company

        # 종목코드가 없거나 매칭 실패 시 정확한 회사명
        exact_matches = [
            company
            for company in companies
            if company["corp_name"] == corp_name
        ]

        if len(exact_matches) == 1:
            return exact_matches[0]

        return None