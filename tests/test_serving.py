import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from peerproof.serving import builders as b  # noqa: E402

try:
    from fastapi.testclient import TestClient
    from peerproof.api.app import create_app
    HAVE_FASTAPI = True
except Exception:  # pragma: no cover
    HAVE_FASTAPI = False

SPEC = importlib.util.spec_from_file_location("build_serving_data", ROOT / "scripts" / "build_serving_data.py")
bs = importlib.util.module_from_spec(SPEC)
sys.modules["build_serving_data"] = bs
SPEC.loader.exec_module(bs)


def unified(name="대상", corp="00000001", cutoff="2023-12-21"):
    return {
        "schema_version": "peerproof_profile_unified_v1", "analysis_as_of": cutoff, "built_at": "2026-01-01T00:00:00+09:00",
        "company": {"company_name": name, "corp_code": corp, "stock_code": "123456"},
        "source_reports": {"quarterly": {"report_name": "분기보고서 (2023.09)", "rcept_no": "20231114001221", "rcept_date": "20231114"}},
        "business_model": {
            "revenue_model": {"label": "매출 구조", "status": "확인", "value": "직접 판매",
                              "evidence": [{"evidence_id": "E1", "text": "가" * 400,
                                            "source": {"chunk_id": "c1", "report": "분기보고서 (2023.09)", "rcept_no": "20231114001221",
                                                       "filing_date": "2023-11-14", "section": "II. 사업의 내용", "page": 3}}]},
            "customer_type": {"label": "고객 유형", "status": "미공시", "value": None, "evidence": []},
            "products_services": {"label": "제품", "status": "확인", "value": {"A": ["x", "y"], "B": "z"}, "evidence": []},
        },
        "growth": {},
        "risk": {"competition": {"label": "경쟁", "status": "확인", "value": "치열",
                                 "evidence": [{"evidence_id": "E1", "chunk_id": "c1"}]}},
        "growth_metrics": {
            "revenue": {"value": 371_789_961_905, "status": "확인", "source": {"rcept_no": "20231114001221", "filing_date": "2023-11-14", "period": "p"}, "note": "n"},
            "revenue_growth_rate": {"value": 0.3791, "status": "확인", "source": {}, "note": None},
            "overseas_revenue_ratio": {"value": None, "status": "미확인", "source": {}, "note": "표 없음"},
        },
        "financial_raw": {"period_context": {"rcept_no": "20231114001221", "rcept_date": "2023-11-14", "report_name": "분기보고서 (2023.09)",
                                              "period_start": "2023-01-01", "period_end": "2023-09-30", "fs_div": "CFS"},
                          "accounts": {"revenue": {"label": "매출액", "value": 371_789_961_905, "status": "found"},
                                       "operating_income": {"label": "영업이익", "value": None, "status": "missing"}}},
        "leakage_check": {"passed": True},
    }


CHUNKS = [{"chunk_id": "c1", "report": "분기보고서 (2023.09)", "rcept_no": "20231114001221", "filing_date": "2023-11-14",
           "section": "II. 사업의 내용 > 4. 매출", "page": 25, "content": "청크 본문"}]


class FormatTests(unittest.TestCase):
    def test_values(self):
        self.assertEqual(b.format_krw(371_789_961_905), "3,717.9억원")
        self.assertEqual(b.format_krw(5_000_000), "5,000,000원")
        self.assertEqual(b.metric_value("revenue_growth_rate", 0.3791), "37.9%")
        self.assertIsNone(b.metric_value("revenue", None))
        self.assertEqual(b.display_value({"A": ["x", "y"], "B": "z"}), "A: x, y\nB: z")
        self.assertIsNone(b.display_value(None))


class ProfileTests(unittest.TestCase):
    def test_profile_shape_matches_frontend_adapter(self):
        p = b.build_profile(unified(), CHUNKS)
        self.assertEqual((p["company_id"], p["company_name"]), ("00000001", "대상"))
        self.assertEqual([s["key"] for s in p["sections"]], ["business_model", "growth", "risk", "growth_metrics", "financial_raw"])
        ids = {e["id"] for e in p["evidence"]}
        self.assertEqual(len(ids), len(p["evidence"]))  # 근거 id 중복 없음
        for section in p["sections"]:
            for item in section["items"]:
                self.assertTrue({"key", "label", "value", "status", "evidence_ids"} <= set(item))
                self.assertTrue(set(item["evidence_ids"]) <= ids)
        for e in p["evidence"]:
            self.assertTrue(e["id"] and e["source"])
        business = {i["key"]: i for i in p["sections"][0]["items"]}
        self.assertIsNone(business["customer_type"]["value"])  # 프론트 어댑터가 '미확인'으로 채운다
        self.assertEqual(business["products_services"]["value"], "A: x, y\nB: z")
        ev = next(e for e in p["evidence"] if e["id"] == "business_model.revenue_model.E1")
        self.assertEqual(ev["published_at"], "2023-11-14")
        self.assertTrue(ev["url"].endswith("20231114001221"))
        self.assertEqual(ev["locator"], "II. 사업의 내용 · p.3")
        self.assertEqual(len(ev["quote"]), 301)
        risk_ev = next(e for e in p["evidence"] if e["id"] == "risk.competition.E1")
        self.assertEqual(risk_ev["locator"], "II. 사업의 내용 > 4. 매출 · p.25")  # chunk_id로 보충
        self.assertEqual(risk_ev["quote"], "청크 본문")
        metrics = {i["key"]: i["value"] for i in p["sections"][3]["items"]}
        self.assertEqual(metrics["revenue"], "3,717.9억원")
        self.assertIsNone(metrics["overseas_revenue_ratio"])
        json.dumps(p, ensure_ascii=False)


class SimilarTests(unittest.TestCase):
    def test_fusion_and_rank(self):
        bge = {"results": [{"company_name": "가", "corp_code": "1", "bge_similarity": 0.8},
                           {"company_name": "나", "corp_code": "2", "bge_similarity": 0.6},
                           {"company_name": "다", "corp_code": "3", "bge_similarity": 0.9}]}
        net = {"results": [{"company_name": "가", "corp_code": "1", "semantic_keyword_jaccard": 0.2,
                            "soft_weighted_edge_jaccard": 0.2, "weighted_centrality_cosine": 0.8},
                           {"company_name": "나", "corp_code": "2", "semantic_keyword_jaccard": 0.6,
                            "soft_weighted_edge_jaccard": 0.6, "weighted_centrality_cosine": 0.6}]}
        out = b.build_similar("T", bge, net, {"embedding_weight": 0.5, "network_weight": 0.5, "method": "x"})
        by = {i["name"]: i for i in out["items"]}
        self.assertAlmostEqual(by["가"]["network_score"], 0.4)
        self.assertAlmostEqual(by["가"]["fused_score"], 0.6)
        self.assertAlmostEqual(by["나"]["fused_score"], 0.6)
        self.assertEqual(by["다"]["fused_score"], 0.9)  # 네트워크 점수가 없으면 있는 점수만
        self.assertIsNone(by["다"]["network_score"])
        self.assertEqual(out["items"][0]["name"], "다")
        self.assertEqual([i["rank"] for i in out["items"]], [1, 2, 3])
        self.assertEqual(out["fusion"], {"embedding_weight": 0.5, "network_weight": 0.5, "method": "x"})


class MetricsTests(unittest.TestCase):
    def test_ratios(self):
        u = {"company": {"corp_code": "9", "company_name": "x"},
             "growth_metrics": {"revenue_growth_rate": {"value": 0.1}, "overseas_revenue_ratio": {"value": None}},
             "financial_raw": {"accounts": {"revenue": {"value": 200}, "operating_income": {"value": 50},
                                             "net_income_total": {"value": 20}, "total_liabilities": {"value": 300},
                                             "total_equity": {"value": 150}},
                               "period_context": {"period_start": "2023-01-01", "period_end": "2023-09-30", "rcept_no": "1"}}}
        v = b.company_metrics(u)["values"]
        self.assertEqual((v["operating_margin"], v["net_margin"], v["debt_ratio"]), (0.25, 0.1, 2.0))
        self.assertIsNone(v["overseas_revenue_ratio"])
        m = b.build_metrics("9", {"9": u}, {"items": [{"company_id": "missing"}]})
        self.assertEqual(len(m["rows"]), 1)  # 프로필 없는 후보는 건너뜀


class BuildAndApiTests(unittest.TestCase):
    def make_root(self, directory):
        root = Path(directory)
        for name, corp in (("대상", "00000001"), ("후보", "00000002")):
            base = root / "data" / "processed" / name
            (base / "profile").mkdir(parents=True)
            (base / "rag").mkdir(parents=True)
            (base / "profile" / "profile_unified.json").write_text(json.dumps(unified(name, corp), ensure_ascii=False), encoding="utf-8")
            (base / "rag" / "rag_chunks.json").write_text(json.dumps(CHUNKS, ensure_ascii=False), encoding="utf-8")
        listing = root / "list.json"
        listing.write_text(json.dumps([{"company_name": "후보"}, {"company_name": "없는회사"}], ensure_ascii=False), encoding="utf-8")
        bge = root / "bge.json"
        bge.write_text(json.dumps({"results": [{"company_name": "후보", "corp_code": "00000002", "bge_similarity": 0.7}]}), encoding="utf-8")
        return root, listing, bge

    def test_build_requires_weights_for_similarity(self):
        with tempfile.TemporaryDirectory() as d:
            root, listing, bge = self.make_root(d)
            base = ["--target", "대상", "--candidates", str(listing), "--as-of", "20231221", "--root", str(root)]
            self.assertEqual(bs.main(base + ["--bge", str(bge)]), 1)
            self.assertEqual(bs.main(base + ["--bge", str(bge), "--provisional-equal-weights"]), 0)
            sim = json.loads((root / "data" / "serving" / "00000001" / "similar.json").read_text(encoding="utf-8"))
            self.assertEqual(sim["fusion"]["method"], "provisional_equal_weights")
            companies = json.loads((root / "data" / "serving" / "companies.json").read_text(encoding="utf-8"))
            self.assertEqual([c["name"] for c in companies], ["대상", "후보"])

    @unittest.skipUnless(HAVE_FASTAPI, "fastapi 미설치")
    def test_api_serves_files(self):
        with tempfile.TemporaryDirectory() as d:
            root, listing, bge = self.make_root(d)
            bs.main(["--target", "대상", "--candidates", str(listing), "--as-of", "20231221", "--root", str(root),
                     "--bge", str(bge), "--fusion-weights", "1", "1"])
            client = TestClient(create_app(root / "data" / "serving"))
            self.assertEqual(len(client.get("/api/companies").json()), 2)
            self.assertEqual([c["name"] for c in client.get("/api/companies", params={"query": "후"}).json()], ["후보"])
            self.assertEqual(client.get("/api/companies/00000001/profile").json()["company_name"], "대상")
            self.assertEqual(client.get("/api/companies/00000001/similar").json()["items"][0]["name"], "후보")
            self.assertEqual(client.get("/api/companies/00000001/network").json()["nodes"], [])
            self.assertEqual(client.get("/api/companies/00000002/network").json()["nodes"], [])  # 없는 네트워크 -> 빈 값
            self.assertEqual(client.get("/api/companies/00000001/explanations/00000002").json()["similarities"], [])
            self.assertEqual(client.get("/api/companies/99999999/profile").status_code, 404)  # 프로필은 여전히 404
            m = client.get("/api/companies/00000001/metrics").json()
            self.assertEqual([r["is_target"] for r in m["rows"]], [True, False])
            self.assertEqual(m["rows"][0]["values"]["revenue_growth_rate"], 0.3791)
            self.assertIsNone(m["rows"][0]["values"]["operating_margin"])  # 영업이익 없음 -> 계산 불가
            self.assertEqual(client.get("/api/companies/00000001/explanations/..%2Fx").status_code in (400, 404), True)
            self.assertEqual(client.get("/api/companies/00000009/profile").status_code, 404)
            self.assertEqual(client.get("/api/companies/..%2Fx/profile").status_code in (400, 404), True)


if __name__ == "__main__":
    unittest.main()
