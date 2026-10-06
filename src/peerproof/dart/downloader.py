from pathlib import Path

from .client import DartClient


class DisclosureDownloader:
    """
    DART 공시 원문 다운로드.
    """

    def __init__(
        self,
        output_root: str | Path = "data/raw/dart",
    ):
        self.client = DartClient()

        self.output_root = Path(
            output_root
        )

        self.output_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    @staticmethod
    def sanitize_filename(
        text: str,
    ):
        """
        파일명에 사용할 수 없는 문자 제거.
        """

        invalid_chars = [
            "/",
            "\\",
            ":",
            "*",
            "?",
            '"',
            "<",
            ">",
            "|",
        ]

        for char in invalid_chars:
            text = text.replace(
                char,
                "_",
            )

        return text.strip()

    def download_document(
        self,
        rcept_no: str,
        company_name: str,
        report_type: str,
        report_name: str,
        rcept_date: str,
    ):
        """
        DART document.xml 호출 후
        ZIP 그대로 저장.
        """

        response = self.client.get(
            "document.xml",
            params={
                "rcept_no": rcept_no,
            },
        )

        content = response.content

        if not content:
            raise RuntimeError(
                f"빈 공시 원문입니다: {rcept_no}"
            )

        if content[:2] != b"PK":

            preview = content[
                :500
            ].decode(
                "utf-8",
                errors="ignore",
            )

            raise RuntimeError(
                "DART 공시 원문이 ZIP 형식이 아닙니다.\n"
                f"rcept_no = {rcept_no}\n"
                f"{preview}"
            )

        company_name = (
            self.sanitize_filename(
                company_name
            )
        )

        report_name = (
            self.sanitize_filename(
                report_name
            )
        )

        company_dir = (
            self.output_root
            / company_name
        )

        company_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = (
            f"{rcept_date}_"
            f"{report_type}_"
            f"{rcept_no}_"
            f"{report_name}.zip"
        )

        output_path = (
            company_dir
            / filename
        )

        with open(
            output_path,
            "wb",
        ) as file:

            file.write(
                content
            )

        return output_path