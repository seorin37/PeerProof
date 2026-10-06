import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from peerproof.dart.client import DartClient, DartError
from peerproof.dart.filings import collect_filings, list_periodic_filings, resolve_company


def zipped(content, name="report.xml"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, content)
    return buffer.getvalue()


def row(receipt="20240321000964"):
    return {"rcept_no": receipt, "rcept_dt": "20240321",
            "report_nm": "[기재정정]사업보고서 (2023.12)"}


class CollectionTests(unittest.TestCase):
    def test_pagination_and_no_data(self):
        client = Mock()
        client.json.side_effect = [
            {"status": "000", "total_page": 2, "list": [row()]},
            {"status": "000", "total_page": 2, "list": [row("20240321000965")]},
            {"status": "013"},
        ]
        result = list_periodic_filings(client, "01190568", "20230101", "20241231",
                                      ["annual", "semiannual"])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["report_period"], "2023.12")
        self.assertEqual(client.json.call_args_list[1].kwargs["page_no"], 2)
        self.assertEqual(client.json.call_args_list[0].kwargs["last_reprt_at"], "Y")

    def test_company_exact_resolution_and_ambiguity(self):
        client = Mock()
        client.archive.return_value = zipped(
            "<result><list><corp_code>01190568</corp_code><corp_name>에이피알</corp_name>"
            "<stock_code>278470</stock_code><corp_eng_name>APR</corp_eng_name></list>"
            "<list><corp_code>00000001</corp_code><corp_name>에이피알파트너</corp_name>"
            "<stock_code></stock_code></list></result>".encode(), "CORPCODE.xml"
        )
        with tempfile.TemporaryDirectory() as directory:
            company = resolve_company(client, "APR", directory)
            self.assertEqual(company["corp_code"], "01190568")
            self.assertEqual(resolve_company(client, "278470", directory), company)
            with self.assertRaises(DartError):
                resolve_company(client, "에이피", directory)
        self.assertEqual(client.archive.call_count, 1)

    def test_partial_failure_then_resume(self):
        client = Mock()
        client.json.return_value = {"status": "000", "total_page": 1,
                                    "list": [row(), row("20240321000965")]}
        client.archive.side_effect = [zipped(b"<report/>"), DartError("DART error 014")]
        company = {"corp_code": "01190568"}
        with tempfile.TemporaryDirectory() as directory:
            manifest, filings, failures = collect_filings(
                client, company, "20230101", "20241231", directory, ["annual"])
            self.assertTrue(manifest.exists())
            self.assertEqual(failures, ["20240321000965"])
            client.archive.reset_mock()
            client.archive.side_effect = None
            client.archive.return_value = zipped(b"<report/>")
            _, filings, failures = collect_filings(
                client, company, "20230101", "20241231", directory, ["annual"])
            self.assertEqual(failures, [])
            self.assertEqual(client.archive.call_count, 1)

    def test_errors_do_not_expose_key(self):
        client = DartClient(api_key="PRIVATE_TEST_KEY")
        client.session = Mock()
        client.session.get.side_effect = requests.ConnectionError(
            "https://example.invalid/?crtfc_key=PRIVATE_TEST_KEY")
        with self.assertRaises(DartError) as raised:
            client.json("list.json")
        self.assertNotIn("PRIVATE_TEST_KEY", str(raised.exception))

    def test_binary_endpoint_api_error(self):
        client = DartClient(api_key="PRIVATE_TEST_KEY")
        client.session = Mock()
        client.session.get.return_value.content = b"<result><status>010</status></result>"
        with self.assertRaisesRegex(DartError, "010"):
            client.archive("document.xml", rcept_no="20240321000964")


if __name__ == "__main__":
    unittest.main()
