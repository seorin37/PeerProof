import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("compare_methods", ROOT / "scripts" / "compare_methods.py")
cm = importlib.util.module_from_spec(SPEC)
sys.modules["compare_methods"] = cm
SPEC.loader.exec_module(cm)

DEMO = ROOT / "examples" / "compare_demo"


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def fixture(directory):
    d = Path(directory)
    peers = [("가", "00000001"), ("나", "00000002")]
    others = [("다", "00000003"), ("라", "00000004"), ("마", "00000005")]
    write(d / "key.json", {"target_company": "T", "analysis_as_of": "2023-12-21",
                           "peers": [{"company_name": n, "corp_code": c} for n, c in peers]})
    # 임베딩은 가,나가 위 / 네트워크는 다,라가 위
    bge = {"results": [{"company_name": n, "corp_code": c, "bge_similarity": s}
                       for (n, c), s in zip(peers + others, (0.9, 0.8, 0.5, 0.4, 0.3))]}
    net = {"results": [{"company_name": n, "corp_code": c, "semantic_keyword_jaccard": s,
                        "soft_weighted_edge_jaccard": s, "weighted_centrality_cosine": s}
                       for (n, c), s in zip(peers + others, (0.1, 0.2, 0.9, 0.8, 0.7))]}
    write(d / "bge.json", bge)
    write(d / "net.json", net)
    return d


class CompareTests(unittest.TestCase):
    def test_rankings_and_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = fixture(tmp)
            out = d / "out.json"
            code = cm.main(["--answer-key", str(d / "key.json"), "--bge", str(d / "bge.json"),
                            "--network", str(d / "net.json"), "--out", str(out)])
            self.assertEqual(code, 0)
            report = json.loads(out.read_text(encoding="utf-8"))
        m = report["methods"]
        self.assertEqual(m["임베딩만"]["answers_in_top5"], 2)
        self.assertEqual(m["임베딩만"]["mrr"], 1.0)
        self.assertEqual(m["네트워크만(3지표 평균)"]["mrr"], round(1 / 4, 4))  # 정답 최고 순위가 4위
        self.assertIn("융합 임베딩50:네트워크50", m)
        self.assertNotIn("융합 임베딩0:네트워크100", m)  # 양 끝은 단독 방법과 같아서 뺀다
        self.assertEqual(report["selection"]["best_single"], "임베딩만")
        self.assertTrue(report["selection"]["suggested"].startswith("융합"))

    def test_fused_uses_same_formula_as_serving(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = fixture(tmp)
            bge = json.loads((d / "bge.json").read_text(encoding="utf-8"))
            net = json.loads((d / "net.json").read_text(encoding="utf-8"))
        rankings = cm.method_rankings(bge, net, (0.5,))
        first = rankings["융합 임베딩50:네트워크50"][0]
        # 가: (0.5*0.9 + 0.5*0.1) = 0.5, 다: (0.5*0.5+0.5*0.9)=0.7 -> 다가 1위
        self.assertEqual(first["name"], "다")
        self.assertAlmostEqual(first["score"], 0.7)

    def test_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = fixture(tmp)
            write(d / "cand.json", {"candidates": [{"company_name": "가", "corp_code": "00000001", "role": "A"},
                                                    {"company_name": "마", "corp_code": "00000005", "role": "C"}]})
            out = d / "o.json"
            cm.main(["--answer-key", str(d / "key.json"), "--bge", str(d / "bge.json"), "--network", str(d / "net.json"),
                     "--candidates", str(d / "cand.json"), "--out", str(out)])
            groups = json.loads(out.read_text(encoding="utf-8"))["groups"]
        self.assertEqual(groups["A"]["가"]["임베딩만"], 1)
        self.assertEqual(groups["C"]["마"]["임베딩만"], 5)

    def test_single_input_ok_and_requires_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = fixture(tmp)
            self.assertEqual(cm.main(["--answer-key", str(d / "key.json"), "--bge", str(d / "bge.json")]), 0)
            with self.assertRaises(SystemExit):
                cm.main(["--answer-key", str(d / "key.json")])

    def test_demo_files_run(self):
        self.assertEqual(cm.main(["--answer-key", str(DEMO / "answer_key.json"), "--bge", str(DEMO / "bge_result.json"),
                                  "--network", str(DEMO / "network_result.json"), "--candidates", str(DEMO / "candidates.json")]), 0)


if __name__ == "__main__":
    unittest.main()
