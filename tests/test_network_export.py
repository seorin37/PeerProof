import json
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import networkx as nx
except ImportError:  # pragma: no cover
    nx = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from peerproof.serving.network_export import graph_to_network  # noqa: E402
import build_serving_data as bs  # noqa: E402


@unittest.skipIf(nx is None, "networkx 미설치")
class GraphToNetworkTests(unittest.TestCase):
    def graph(self):
        g = nx.Graph()
        g.add_edge("화장품", "브랜드", weight=3)
        g.add_edge("화장품", "해외", weight=1)
        g.add_edge("브랜드", "해외", weight=2)
        g.add_edge("소모품", "해외", weight=1)
        return g

    def test_shape_and_normalised_centrality(self):
        net = graph_to_network("00000001", self.graph())
        self.assertEqual(net["company_id"], "00000001")
        self.assertEqual({n["id"] for n in net["nodes"]}, {"화장품", "브랜드", "해외", "소모품"})
        values = [n["centrality"] for n in net["nodes"]]
        self.assertEqual(max(values), 1.0)
        self.assertTrue(all(0 <= v <= 1 for v in values))
        self.assertEqual(net["edges"][0]["weight"], 3.0)  # 가장 굵은 간선이 먼저

    def test_max_nodes_drops_edges_to_removed_nodes(self):
        net = graph_to_network("x", self.graph(), max_nodes=2)
        ids = {n["id"] for n in net["nodes"]}
        self.assertEqual(len(ids), 2)
        for e in net["edges"]:
            self.assertIn(e["source"], ids)
            self.assertIn(e["target"], ids)

    def test_empty_graph(self):
        net = graph_to_network("x", nx.Graph())
        self.assertEqual((net["nodes"], net["edges"]), ([], []))


class BuildServingNetworkGraphsTests(unittest.TestCase):
    def test_graphs_copied_for_target_and_candidates(self):
        import test_serving as ts
        with tempfile.TemporaryDirectory() as d:
            helper = ts.BuildAndApiTests()
            root, listing, bge = helper.make_root(d)
            graphs = Path(d) / "graphs"
            graphs.mkdir()
            for cid in ("00000001", "00000002"):
                (graphs / f"{cid}.json").write_text(json.dumps(
                    {"company_id": cid, "nodes": [{"id": "a", "label": "a", "centrality": 1.0}], "edges": []}), encoding="utf-8")
            code = bs.main(["--target", "대상", "--candidates", str(listing), "--as-of", "20231221", "--root", str(root),
                            "--bge", str(bge), "--provisional-equal-weights", "--network-graphs", str(graphs)])
            self.assertEqual(code, 0)
            for cid in ("00000001", "00000002"):
                net = json.loads((root / "data" / "serving" / cid / "network.json").read_text(encoding="utf-8"))
                self.assertEqual(len(net["nodes"]), 1)


if __name__ == "__main__":
    unittest.main()
