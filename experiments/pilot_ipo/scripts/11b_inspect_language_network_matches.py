import json
from pathlib import Path


# =========================================================
# 1. Path
# =========================================================

PROJECT_ROOT = Path("experiments/pilot_ipo")

LANGUAGE_NETWORK_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "language_network_similarity.json"
)


# =========================================================
# 2. 검증할 기업
# =========================================================

SELECTED_COMPANIES = [
    "뷰티스킨",
    "본느",
    "클리오",
    "한국콜마",
    "아우딘퓨쳐스",
    "클래시스",
]


# 출력 개수
TOP_NODE_MATCHES = 10
TOP_EDGE_MATCHES = 10
TOP_KEYWORDS = 10


# =========================================================
# 3. JSON Load
# =========================================================

def load_json(path):

    if not path.exists():

        raise FileNotFoundError(
            f"파일을 찾을 수 없습니다: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# =========================================================
# 4. 기업 찾기
# =========================================================

def find_company_result(
    results,
    company_name
):

    for item in results:

        if (
            item.get("company_name")
            == company_name
        ):

            return item

    return None


# =========================================================
# 5. Target Keyword 출력
# =========================================================

def print_target_keywords(
    target
):

    print()
    print("=" * 100)
    print("APR Target Keywords")
    print("=" * 100)

    keywords = target.get(
        "keywords",
        []
    )

    for rank, item in enumerate(
        keywords[:20],
        start=1
    ):

        print(
            f"{rank:>2}. "
            f"{item.get('keyword', ''):<35} "
            f"freq="
            f"{item.get('frequency', 0):>2} "
            f"score="
            f"{item.get('mean_keybert_score', 0.0):.4f}"
        )


# =========================================================
# 6. Candidate Keyword 출력
# =========================================================

def print_candidate_keywords(
    result
):

    print()
    print("[Candidate Top Keywords]")
    print("-" * 100)

    keywords = result.get(
        "keywords",
        []
    )

    for rank, item in enumerate(
        keywords[:TOP_KEYWORDS],
        start=1
    ):

        print(
            f"{rank:>2}. "
            f"{item.get('keyword', ''):<35} "
            f"freq="
            f"{item.get('frequency', 0):>2} "
            f"score="
            f"{item.get('mean_keybert_score', 0.0):.4f}"
        )


# =========================================================
# 7. Semantic Node Match 출력
#
# APR keyword와 후보기업 keyword가
# 의미적으로 어떤 식으로 매칭되었는지 확인
# =========================================================

def print_node_matches(
    result
):

    print()
    print("[Semantic Node Matches]")
    print("-" * 100)

    matches = result.get(
        "semantic_node_matches",
        []
    )

    matches = sorted(
        matches,
        key=lambda item:
            item.get(
                "similarity",
                0.0
            ),
        reverse=True
    )

    if not matches:

        print(
            "Node match 없음"
        )

        return

    for rank, item in enumerate(
        matches[:TOP_NODE_MATCHES],
        start=1
    ):

        target_keyword = (
            item.get(
                "target_keyword",
                ""
            )
        )

        candidate_keyword = (
            item.get(
                "candidate_keyword",
                ""
            )
        )

        similarity = float(
            item.get(
                "similarity",
                0.0
            )
        )

        print(
            f"{rank:>2}. "
            f"APR: {target_keyword}"
        )

        print(
            f"    Candidate: "
            f"{candidate_keyword}"
        )

        print(
            f"    similarity: "
            f"{similarity:.4f}"
        )

        print()


# =========================================================
# 8. Semantic Edge Match 출력
#
# APR의 keyword 관계와
# 후보기업의 keyword 관계가
# 어떤 식으로 매칭되었는지 확인
# =========================================================

def print_edge_matches(
    result
):

    print()
    print("[Semantic Edge Matches]")
    print("-" * 100)

    matches = result.get(
        "semantic_edge_matches",
        []
    )

    matches = sorted(
        matches,
        key=lambda item:
            item.get(
                "semantic_similarity",
                0.0
            ),
        reverse=True
    )

    if not matches:

        print(
            "Edge match 없음"
        )

        return

    for rank, item in enumerate(
        matches[:TOP_EDGE_MATCHES],
        start=1
    ):

        target_edge = item.get(
            "target_edge",
            []
        )

        candidate_edge = item.get(
            "candidate_edge",
            []
        )

        semantic_similarity = float(
            item.get(
                "semantic_similarity",
                0.0
            )
        )

        target_weight = float(
            item.get(
                "target_weight",
                0.0
            )
        )

        candidate_weight = float(
            item.get(
                "candidate_weight",
                0.0
            )
        )

        matched_mass = float(
            item.get(
                "matched_mass",
                0.0
            )
        )


        if len(target_edge) == 2:

            target_text = (
                f"{target_edge[0]}"
                f"  ─  "
                f"{target_edge[1]}"
            )

        else:

            target_text = str(
                target_edge
            )


        if len(candidate_edge) == 2:

            candidate_text = (
                f"{candidate_edge[0]}"
                f"  ─  "
                f"{candidate_edge[1]}"
            )

        else:

            candidate_text = str(
                candidate_edge
            )


        print(
            f"{rank:>2}. APR"
        )

        print(
            f"    {target_text}"
        )

        print()

        print(
            f"    Candidate"
        )

        print(
            f"    {candidate_text}"
        )

        print()

        print(
            f"    semantic similarity : "
            f"{semantic_similarity:.4f}"
        )

        print(
            f"    APR edge weight      : "
            f"{target_weight:.1f}"
        )

        print(
            f"    Candidate edge weight: "
            f"{candidate_weight:.1f}"
        )

        print(
            f"    matched mass         : "
            f"{matched_mass:.4f}"
        )

        print()


# =========================================================
# 9. Graph Summary
# =========================================================

def print_graph_summary(
    result
):

    graph = result.get(
        "graph",
        {}
    )

    print()
    print("[Graph Summary]")
    print("-" * 100)

    print(
        f"Nodes               : "
        f"{graph.get('node_count', 0)}"
    )

    print(
        f"Edges               : "
        f"{graph.get('edge_count', 0)}"
    )

    print(
        f"Density             : "
        f"{graph.get('density', 0.0):.4f}"
    )

    print(
        f"Average Clustering  : "
        f"{graph.get('average_clustering', 0.0):.4f}"
    )

    print()
    print(
        "Top Central Keywords"
    )

    top_central = graph.get(
        "top_central_keywords",
        []
    )

    for rank, item in enumerate(
        top_central,
        start=1
    ):

        print(
            f"{rank:>2}. "
            f"{item.get('keyword', ''):<35} "
            f"weighted_degree="
            f"{item.get('weighted_degree', 0.0):.2f}"
        )


# =========================================================
# 10. Score Summary
# =========================================================

def print_score_summary(
    result
):

    print()
    print("[Similarity Score]")
    print("-" * 100)

    print(
        f"Semantic Keyword Jaccard : "
        f"{result.get('semantic_keyword_jaccard', 0.0):.4f}"
    )

    print(
        f"Soft Edge Jaccard        : "
        f"{result.get('soft_weighted_edge_jaccard', 0.0):.4f}"
    )

    print(
        f"Weighted Centrality      : "
        f"{result.get('weighted_centrality_cosine', 0.0):.4f}"
    )

    print()

    print(
        f"Keyword Rank             : "
        f"{result.get('keyword_rank', '-')}"
    )

    print(
        f"Edge Rank                : "
        f"{result.get('edge_rank', '-')}"
    )

    print(
        f"Centrality Rank          : "
        f"{result.get('centrality_rank', '-')}"
    )

    print()

    print(
        f"Semantic Node Match Count: "
        f"{result.get('semantic_node_match_count', 0)}"
    )

    print(
        f"Semantic Edge Match Count: "
        f"{result.get('semantic_edge_match_count', 0)}"
    )


# =========================================================
# 11. 기업 전체 출력
# =========================================================

def inspect_company(
    result
):

    company_name = result.get(
        "company_name",
        ""
    )

    stock_code = result.get(
        "stock_code",
        ""
    )

    print()
    print()
    print("#" * 100)

    print(
        f"{company_name} "
        f"({stock_code})"
    )

    print("#" * 100)


    print_score_summary(
        result
    )


    print_candidate_keywords(
        result
    )


    print_node_matches(
        result
    )


    print_edge_matches(
        result
    )


    print_graph_summary(
        result
    )


# =========================================================
# 12. Main
# =========================================================

def main():

    print()
    print("=" * 100)

    print(
        "PeerProof - Language Network "
        "Match Inspection"
    )

    print("=" * 100)


    data = load_json(
        LANGUAGE_NETWORK_PATH
    )


    target = data.get(
        "target",
        {}
    )


    results = data.get(
        "results",
        []
    )


    config = data.get(
        "config",
        {}
    )


    print()

    print(
        f"Target Company      : "
        f"{target.get('company_name')}"
    )

    print(
        f"Candidate Count     : "
        f"{len(results)}"
    )

    print(
        f"Node Threshold      : "
        f"{config.get('node_match_threshold')}"
    )

    print(
        f"Edge Threshold      : "
        f"{config.get('edge_match_threshold')}"
    )


    # -----------------------------------------------------
    # APR Keyword
    # -----------------------------------------------------

    print_target_keywords(
        target
    )


    # -----------------------------------------------------
    # Selected Company
    # -----------------------------------------------------

    for company_name in SELECTED_COMPANIES:

        result = find_company_result(
            results,
            company_name
        )

        if result is None:

            print()
            print(
                f"[WARNING] "
                f"{company_name} 결과를 "
                f"찾지 못했습니다."
            )

            continue


        inspect_company(
            result
        )


    print()
    print()
    print("=" * 100)
    print(
        "Inspection Complete"
    )
    print("=" * 100)


if __name__ == "__main__":
    main()
