import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_profile", ROOT / "scripts" / "build_profile.py")
bp = importlib.util.module_from_spec(SPEC)
sys.modules["build_profile"] = bp
SPEC.loader.exec_module(bp)

COMPANY = "테스트기업"
PARAMS = {"company": COMPANY, "stock_code": "000000", "ipo_date": "20231222", "cutoff": "2023-12-21"}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def evidence(rcept, date, eid="E1"):
    return {"evidence_id": eid, "text": "x", "source": {"rcept_no": rcept, "filing_date": date}}


def make_company(root, *, selected_date="20231114", evidence_date="2023-11-14", ipo_date="20231222"):
    raw = root / "data" / "raw" / "dart" / COMPANY
    write(raw / "metadata.json", {
        "company": {"corp_name": COMPANY, "corp_code": "00000001", "stock_code": "000000"},
        "collection_rule": {"ipo_date": ipo_date, "cutoff_date": "20231221"},
        "selected_reports": {
            "quarterly": {"report_name": "분기보고서 (2023.09)", "rcept_no": "20231114001221", "rcept_date": selected_date},
        },
    })
    profile = root / "data" / "processed" / COMPANY / "profile"
    write(profile / "business_v2" / "business_profile_v2.json", {
        "summary": {"completed_features": 2, "total_features": 2},
        "business": {
            "products_services": {"code": "B1", "status": "확인", "value": "a",
                                  "evidence": [evidence("20231114001221", evidence_date)]},
            "revenue_model": {"code": "B2", "status": "부분확인", "value": "b", "evidence": []},
        },
    })
    write(profile / "company_profile_v2.json", {
        "profile": {
            "growth": {},
            "risk": {
                "customer_concentration": {"status": "미공시", "value": None, "evidence": [{"evidence_id": "R1", "text": "t"}]},
            },
        }
    })
    finance = root / "data" / "processed" / COMPANY / "finance"
    write(finance / "finance_latest.json", {
        "companies": {"00000001": {"context": {"period": "2023Q3"},
                                   "accounts": {"revenue": {"value": 100, "status": "ok"}}}},
    })
    return bp.Paths(root, COMPANY)


class CutoffTests(unittest.TestCase):
    def test_cutoff_is_previous_day(self):
        self.assertEqual(bp.compute_cutoff("20231222"), "2023-12-21")
        self.assertEqual(bp.compute_cutoff("20240101"), "2023-12-31")

    def test_invalid_date(self):
        with self.assertRaises(ValueError):
            bp.compute_cutoff("2023-12-22")


class StateTests(unittest.TestCase):
    def test_mismatched_params_abort(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = bp.Paths(Path(directory), COMPANY)
            bp.save_json(paths.state, {"params": PARAMS, "steps": {}})
            changed = {**PARAMS, "ipo_date": "20240101", "cutoff": "2023-12-31"}
            with self.assertRaises(SystemExit):
                bp.load_state(paths, changed)
            self.assertEqual(bp.load_state(paths, PARAMS)["params"], PARAMS)


class AssembleTests(unittest.TestCase):
    def test_assemble_counts_and_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = make_company(Path(directory))
            unified = bp.assemble(paths, PARAMS, None)
            self.assertEqual(unified["schema_version"], bp.UNIFIED_SCHEMA)
            self.assertEqual(unified["company"]["corp_code"], "00000001")
            self.assertEqual(unified["completeness"]["business_model"]["by_status"], {"확인": 1, "부분확인": 1})
            self.assertEqual(unified["completeness"]["growth"]["total"], 0)
            self.assertEqual(unified["financial_raw"]["accounts"]["revenue"]["value"], 100)
            self.assertEqual(unified["financial_raw"]["accounts"]["operating_income"]["status"], "missing")
            check = unified["leakage_check"]
            self.assertTrue(check["passed"])
            self.assertEqual(check["evidence_checked"], 1)
            self.assertEqual(check["evidence_without_filing_date"], 1)
            self.assertTrue(paths.unified.exists())

    def test_selected_report_after_cutoff_is_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = make_company(Path(directory), selected_date="20231222")
            check = bp.assemble(paths, PARAMS, None)["leakage_check"]
            self.assertFalse(check["passed"])
            self.assertEqual(check["violations"][0]["kind"], "selected_report_after_cutoff")

    def test_evidence_after_cutoff_is_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = make_company(Path(directory), evidence_date="2024-02-13")
            check = bp.assemble(paths, PARAMS, None)["leakage_check"]
            self.assertFalse(check["passed"])
            self.assertEqual(check["violations"][0]["kind"], "evidence_after_cutoff")

    def test_evidence_from_unselected_report_is_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = make_company(Path(directory))
            data = bp.load_json(paths.business_v2)
            data["business"]["products_services"]["evidence"] = [evidence("20240101000001", "2023-11-14")]
            bp.save_json(paths.business_v2, data)
            check = bp.assemble(paths, PARAMS, None)["leakage_check"]
            self.assertEqual(check["violations"][0]["kind"], "evidence_report_not_selected")

    def test_chunk_id_supplies_missing_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = make_company(Path(directory))
            data = bp.load_json(paths.company_profile)
            data["profile"]["risk"]["customer_concentration"]["evidence"] = [
                {"evidence_id": "R1", "chunk_id": "c1", "text": "t"}
            ]
            bp.save_json(paths.company_profile, data)
            bp.save_json(paths.chunks, [{"chunk_id": "c1", "rcept_no": "20231114001221", "filing_date": "2023-11-14"}])
            check = bp.assemble(paths, PARAMS, None)["leakage_check"]
            self.assertTrue(check["passed"])
            self.assertEqual(check["evidence_checked"], 2)
            self.assertEqual(check["evidence_without_filing_date"], 0)
            bp.save_json(paths.chunks, [{"chunk_id": "c1", "rcept_no": "20240213000787", "filing_date": "2024-02-13"}])
            check = bp.assemble(paths, PARAMS, None)["leakage_check"]
            self.assertFalse(check["passed"])


class OutputsTests(unittest.TestCase):
    def test_download_requires_same_ipo_date(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = make_company(Path(directory), ipo_date="20240101")
            self.assertFalse(bp.outputs_ready("download", paths, PARAMS))
            self.assertTrue(bp.outputs_ready("download", paths, {**PARAMS, "ipo_date": "20240101"}))

    def test_business_v2_requires_all_features(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = make_company(Path(directory))
            self.assertTrue(bp.business_v2_complete(paths))
            data = bp.load_json(paths.business_v2)
            data["summary"]["completed_features"] = 1
            bp.save_json(paths.business_v2, data)
            self.assertFalse(bp.business_v2_complete(paths))

    def test_growth_and_risk_ready_only_when_non_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = make_company(Path(directory))
            self.assertFalse(bp.outputs_ready("growth", paths, PARAMS))
            self.assertTrue(bp.outputs_ready("risk", paths, PARAMS))


TABLE = (
    "가. 매출실적 <!-- t --> | (단위: 백만원) | | --- | "
    "| 구분 | 2023년 3분기 | 2022년 | 비고 | "
    "| 제품 | 내수 | 221,631 | 246,000 | - | | 수출 | 138,728 | 143,659 | - | | | 계 | 360,360 | 389,660 | | "
    "| 합계 | 내수 | 233,061 | 254,039 | - | | 수출 | 138,728 | 143,659 | - | | | 계 | 371,790 | 397,698 | - | | "
    "※ 상기 매출실적은 연결기준으로 작성되었습니다."
)


class GrowthMetricsTests(unittest.TestCase):
    def setup(self, directory, table=TABLE, revenue=371_789_961_905, previous=269_585_916_164):
        paths = make_company(Path(directory))
        bp.save_json(paths.chunks, [{
            "chunk_id": "s1", "section": "II. 사업의 내용 > 4. 매출 및 수주상황 > 가. 매출실적",
            "rcept_no": "20231114001221", "filing_date": "2023-11-14", "period": "p", "content": table,
        }])
        bp.save_json(paths.finance / "finance_profile.json", {
            "latest_period": "2023_Q3_YTD",
            "periods": {"2023_Q3_YTD": {"accounts": {"revenue": {"status": "found", "previous_value": previous}}}},
        })
        company = {"context": {"rcept_no": "20231114001221", "rcept_date": "2023-11-14",
                               "period_start": "2023-01-01", "period_end": "2023-09-30"},
                   "accounts": {"revenue": {"value": revenue}}}
        return paths, company

    def test_parse_sales_table(self):
        parsed = bp.parse_sales_table(TABLE)
        self.assertEqual(parsed, {"domestic": 233_061_000_000, "overseas": 138_728_000_000, "total": 371_790_000_000})
        self.assertIsNone(bp.parse_sales_table("표 없음"))
        self.assertIsNone(bp.parse_sales_table(TABLE.replace("(단위: 백만원)", "")))

    def test_all_metrics_confirmed(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, company = self.setup(directory)
            m = bp.growth_metrics(paths, company, "2023-12-21")
            self.assertEqual(m["previous_period_revenue"]["value"], 269_585_916_164)
            self.assertAlmostEqual(m["revenue_growth_rate"]["value"], 0.3791, places=4)
            self.assertEqual(m["overseas_revenue"]["value"], 138_728_000_000)
            self.assertEqual(m["overseas_revenue"]["status"], "확인")
            self.assertAlmostEqual(m["overseas_revenue_ratio"]["value"], 0.3731, places=4)

    def test_table_not_matching_revenue_is_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, company = self.setup(directory, revenue=500_000_000_000)
            m = bp.growth_metrics(paths, company, "2023-12-21")
            self.assertEqual(m["overseas_revenue"]["status"], "부분확인")

    def test_missing_table_and_previous_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, company = self.setup(directory, table="표 없음", previous=None)
            m = bp.growth_metrics(paths, company, "2023-12-21")
            self.assertIsNone(m["overseas_revenue"]["value"])
            self.assertEqual(m["overseas_revenue"]["status"], "미확인")
            self.assertIsNone(m["previous_period_revenue"]["value"])
            self.assertIsNone(m["revenue_growth_rate"]["value"])

    def test_table_after_cutoff_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, company = self.setup(directory)
            m = bp.growth_metrics(paths, company, "2023-11-01")
            self.assertEqual(m["overseas_revenue"]["status"], "미확인")


class MainTests(unittest.TestCase):
    def run_main(self, root, *extra):
        argv = ["--company", COMPANY, "--stock-code", "000000", "--ipo-date", "20231222",
                "--root", str(root), *extra]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = bp.main(argv)
        return code, buffer.getvalue()

    def test_assemble_only_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            make_company(Path(directory))
            code, _ = self.run_main(directory, "--assemble-only")
            self.assertEqual(code, 0)
        with tempfile.TemporaryDirectory() as directory:
            make_company(Path(directory), selected_date="20231222")
            code, output = self.run_main(directory, "--assemble-only")
            self.assertEqual(code, 2)
            self.assertIn("실패", output)

    def test_dry_run_lists_steps_and_runs_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.run_main(directory, "--dry-run", "--to-step", "risk")
            self.assertEqual(code, 0)
            for key in ("download", "embeddings", "business_v2", "growth", "risk"):
                self.assertIn(key, output)
            self.assertNotIn("fin_latest", output)
            self.assertFalse((Path(directory) / "data" / "processed" / ".build_state").exists())

    def test_adopt_existing_marks_finished_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = make_company(Path(directory))
            code, output = self.run_main(directory, "--adopt-existing", "--dry-run", "--to-step", "download")
            self.assertEqual(code, 0)
            self.assertIn("download", output)
            self.assertFalse(paths.state.exists())  # dry-run은 상태를 저장하지 않는다
            code, output = self.run_main(directory, "--adopt-existing", "--to-step", "download")
            self.assertTrue(paths.state.exists())
            state = bp.load_json(paths.state)
            self.assertIn("download", state["steps"])
            self.assertIn("business_v2", state["steps"])
            self.assertNotIn("growth", state["steps"])  # 비어 있는 growth는 인정하지 않는다

    def test_as_of_equals_ipo_date_next_day(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = bp.Paths(Path(directory), COMPANY)
            bp.save_json(paths.state, {"params": PARAMS, "steps": {}})
            argv = ["--company", COMPANY, "--stock-code", "000000", "--as-of", "20231221",
                    "--root", directory, "--dry-run"]
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(bp.main(argv), 0)  # 같은 파라미터라 거부되지 않는다
            self.assertIn("2023-12-21", buffer.getvalue())

    def test_as_of_and_ipo_date_are_exclusive_and_required(self):
        base = ["--company", COMPANY, "--stock-code", "000000", "--dry-run"]
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                bp.parse_args(base)
            with self.assertRaises(SystemExit):
                bp.parse_args(base + ["--as-of", "20231221", "--ipo-date", "20231222"])

    def test_stock_code_is_optional_and_passed_blank(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = ["--company", "미상장기업", "--as-of", "20231221", "--root", directory, "--dry-run"]
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(bp.main(argv), 0)
            self.assertIn("종목코드 없음", buffer.getvalue())
            paths = bp.Paths(Path(directory), "미상장기업")
            params = {"company": "미상장기업", "stock_code": "", "ipo_date": "20231222", "cutoff": "2023-12-21"}
            stdin = bp.build_steps(paths, params, None)["download"]["stdin"]
            self.assertEqual(stdin, "미상장기업\n\n\n20231222\n")

    def test_corp_code_is_passed_to_download_but_not_part_of_state(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = bp.Paths(Path(directory), COMPANY)
            params = {"company": COMPANY, "stock_code": "", "ipo_date": "20231222", "cutoff": "2023-12-21"}
            bp.save_json(paths.state, {"params": params, "steps": {}})
            argv = ["--company", COMPANY, "--corp-code", "01190568", "--as-of", "20231221",
                    "--root", directory, "--dry-run"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bp.main(argv), 0)  # corp_code가 달라도 같은 실행으로 본다
            stdin = bp.build_steps(paths, {**params, "corp_code": "01190568"}, None)["download"]["stdin"]
            self.assertEqual(stdin, f"{COMPANY}\n\n01190568\n20231222\n")

    def test_changed_ipo_date_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = make_company(Path(directory))
            bp.save_json(paths.state, {"params": PARAMS, "steps": {}})
            argv = ["--company", COMPANY, "--stock-code", "000000", "--ipo-date", "20240102",
                    "--root", directory, "--dry-run"]
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                bp.main(argv)


if __name__ == "__main__":
    unittest.main()