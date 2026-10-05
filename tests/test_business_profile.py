import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from peerproof.profile.builder import build_business_profile
from peerproof.profile.schema import FIELDS, GROUPS, OBSERVATION_FIELDS
from peerproof.profile.server import ProfileStore, create_server


def sample():
    return {"company_name": "테스트기업", "analysis_as_of": "2024-02-13", "items": {
        key: {"value": "테스트용 값", "evidence": "테스트용 원문 근거", "report_name": "테스트보고서",
              "received_date": "2024-02-12", "section": "II. 사업의 내용",
              "link": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20240212000000"}
        for key in FIELDS}}


class ProfileTests(unittest.TestCase):
    def test_exact_minimum_contract(self):
        self.assertEqual([len(group["fields"]) for group in GROUPS], [5, 5, 6, 6])
        self.assertEqual(len(FIELDS), 22)
        self.assertEqual(set(OBSERVATION_FIELDS), {"value", "evidence", "report_name", "received_date", "section", "link"})
        profile = build_business_profile(sample())
        self.assertEqual(profile["schema_version"], 2)
        self.assertEqual(set(profile["sections"]), {"business_model", "growth", "risk", "financial_raw_data"})
        for group in GROUPS:
            for key, label in group["fields"]:
                self.assertEqual(profile["sections"][group["id"]][key], {"label": label, **sample()["items"][key]})

    def test_every_observation_requires_every_provenance_field(self):
        for key in FIELDS:
            for field in OBSERVATION_FIELDS:
                value = sample()
                del value["items"][key][field]
                with self.subTest(item=key, field=field), self.assertRaises(ValueError):
                    build_business_profile(value)
        for key in FIELDS:
            value = sample()
            del value["items"][key]
            with self.subTest(item=key), self.assertRaises(ValueError):
                build_business_profile(value)

    def test_revenue_contexts_keep_distinct_values_and_evidence(self):
        value = sample()
        value["items"]["growth_revenue"]["value"] = "2023 3분기 100억 원 (연결)"
        value["items"]["financial_revenue"]["value"] = "2022 연간 300억 원 (별도)"
        value["items"]["financial_revenue"]["section"] = "III. 재무에 관한 사항"
        profile = build_business_profile(value)
        self.assertEqual(profile["manual_profile"]["items"], value["items"])
        self.assertEqual(profile["sections"]["financial_raw_data"]["financial_revenue"]["section"], "III. 재무에 관한 사항")
        self.assertNotIn("300억", profile["business_profile"]["profile_text"])
        self.assertIn("Product / Service", profile["business_profile"]["profile_text"])
        self.assertEqual(profile["review"]["status"], "unreviewed")

    def test_invalid_dates_links_and_future_filings(self):
        for field, invalid in (("received_date", "2024-02-30"), ("received_date", "2024-02-14"),
                               ("received_date", "20240212"), ("link", "javascript:alert(1)"),
                               ("link", "https://"), ("evidence", " "), ("value", 42),
                               ("link", "https://user:secret@example.com/report")):
            value = sample()
            value["items"]["regulation"][field] = invalid
            with self.subTest(field=field, value=invalid), self.assertRaises(ValueError):
                build_business_profile(value)
        value = sample()
        value["items"]["unexpected"] = {}
        with self.assertRaises(ValueError):
            build_business_profile(value)

    def test_save_reload_update_and_invalid_update_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProfileStore(directory)
            saved = store.save(sample())
            self.assertEqual(ProfileStore(directory).get(saved["id"]), saved)
            value = sample()
            value["items"]["customer_type"]["value"] = "제조업체"
            edited = store.save(value, saved["id"])
            self.assertEqual(edited["id"], saved["id"])
            self.assertEqual(len(store.list()), 1)
            value["items"]["customer_type"]["evidence"] = ""
            with self.assertRaises(ValueError):
                store.save(value, saved["id"])
            self.assertEqual(store.get(saved["id"]), edited)
            with self.assertRaises(ValueError):
                store.get("../outside")
            with self.assertRaises(FileNotFoundError):
                store.save(sample(), "a" * 32)


class APITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.server = create_server(self.directory.name, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def request(self, path, method="GET", data=None, headers=None):
        request = Request(self.base + path, method=method,
                          data=json.dumps(data).encode() if data is not None else None,
                          headers=headers or {"Content-Type": "application/json"})
        return urlopen(request, timeout=3)

    def test_schema_editor_create_read_update(self):
        with self.request("/") as response:
            self.assertIn("보고서명".encode(), response.read())
        with self.request("/api/schema") as response:
            self.assertEqual(json.load(response)["groups"], GROUPS)
        with self.request("/api/profiles", "POST", sample()) as response:
            self.assertEqual(response.status, 201)
            saved = json.load(response)
        with self.request("/api/profiles/" + saved["id"]) as response:
            self.assertEqual(json.load(response), saved)
        value = sample()
        value["items"]["competition"]["evidence"] = "경쟁 상황에 관한 수정 근거"
        with self.request("/api/profiles/" + saved["id"], "PUT", value) as response:
            self.assertEqual(json.load(response)["sections"]["risk"]["competition"]["evidence"], "경쟁 상황에 관한 수정 근거")
        with self.request("/api/profiles") as response:
            self.assertEqual(len(json.load(response)), 1)

    def test_reject_cross_site_write_and_invalid_payload(self):
        for data, headers, expected in (
            (sample(), {"Content-Type": "application/json", "Origin": "https://other.example"}, 403),
            (sample(), {"Content-Type": "text/plain"}, 415),
            ({"company_name": ""}, None, 400), ([], None, 400),
        ):
            with self.subTest(expected=expected), self.assertRaises(HTTPError) as error:
                self.request("/api/profiles", "POST", data, headers)
            self.assertEqual(error.exception.code, expected)
            error.exception.close()


if __name__ == "__main__":
    unittest.main()
