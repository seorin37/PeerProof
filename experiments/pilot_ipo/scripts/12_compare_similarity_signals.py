import json
import csv
from pathlib import Path
from statistics import mean


# =========================================================
# 1. Path
# =========================================================

PROJECT_ROOT = Path(
    "experiments/pilot_ipo"
)

BGE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "bge_similarity.json"
)

NETWORK_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "language_network_similarity.json"
)

OUTPUT_JSON = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "similarity_signal_comparison.json"
)

OUTPUT_CSV = (
    PROJECT_ROOT
    / "outputs"
    / "similarity_signal_comparison.csv"
)


# =========================================================
# 2. Config
# =========================================================

TOP_N = 20


# =========================================================
# 3. JSON
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


def save_json(
    path,
    data
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# 4. BGE 결과 읽기
# =========================================================

def load_bge_results():

    data = load_json(
        BGE_PATH
    )

    results = data.get(
        "results",
        []
    )

    if not results:
        raise ValueError(
            "bge_similarity.json에 results가 없습니다."
        )

    # 혹시 rank가 없다면 직접 계산
    ranked = sorted(
        results,
        key=lambda x:
            x.get(
                "similarity",
                0.0
            ),
        reverse=True
    )

    rank_map = {}

    for rank, item in enumerate(
        ranked,
        start=1
    ):

        stock_code = (
            item.get(
                "stock_code"
            )
        )

        rank_map[
            stock_code
        ] = rank

    output = {}

    for item in results:

        stock_code = (
            item.get(
                "stock_code"
            )
        )

        output[
            stock_code
        ] = {
            "company_name":
                item.get(
                    "company_name"
                ),

            "stock_code":
                stock_code,

            "bge_score":
                float(
                    item.get(
                        "similarity",
                        0.0
                    )
                ),

            "bge_rank":
                rank_map.get(
                    stock_code
                ),

            "bge_core_count":
                item.get(
                    "core_evidence_count",
                    item.get(
                        "core_count"
                    )
                ),
        }

    return output


# =========================================================
# 5. Language Network 결과 읽기
# =========================================================

def load_network_results():

    data = load_json(
        NETWORK_PATH
    )

    results = data.get(
        "results",
        []
    )

    if not results:
        raise ValueError(
            "language_network_similarity.json에 "
            "results가 없습니다."
        )

    output = {}

    for item in results:

        stock_code = (
            item.get(
                "stock_code"
            )
        )

        output[
            stock_code
        ] = {
            "company_name":
                item.get(
                    "company_name"
                ),

            "stock_code":
                stock_code,

            "keyword_score":
                float(
                    item.get(
                        "semantic_keyword_jaccard",
                        0.0
                    )
                ),

            "keyword_rank":
                item.get(
                    "keyword_rank"
                ),

            "edge_score":
                float(
                    item.get(
                        "soft_weighted_edge_jaccard",
                        0.0
                    )
                ),

            "edge_rank":
                item.get(
                    "edge_rank"
                ),

            "centrality_score":
                float(
                    item.get(
                        "weighted_centrality_cosine",
                        0.0
                    )
                ),

            "centrality_rank":
                item.get(
                    "centrality_rank"
                ),

            "node_match_count":
                item.get(
                    "semantic_node_match_count",
                    0
                ),

            "edge_match_count":
                item.get(
                    "semantic_edge_match_count",
                    0
                ),
        }

    return output


# =========================================================
# 6. Percentile Score
#
# 점수 스케일이 서로 다르기 때문에
#
# BGE 0.90
# Keyword 0.20
# Edge 0.05
# Centrality 0.30
#
# 를 직접 더하면 안 된다.
#
# 여기서는 우선 순위를 0~1로 변환해
# 비교용 percentile을 만든다.
#
# 중요:
# 아직 Late Fusion 최종점수는 아니다.
# =========================================================

def rank_to_percentile(
    rank,
    total
):

    if (
        rank is None
        or total <= 1
    ):
        return 0.0

    return float(
        (total - rank)
        / (total - 1)
    )


# =========================================================
# 7. 순위 차이
# =========================================================

def calculate_rank_spread(
    row
):

    ranks = [
        row["bge_rank"],
        row["keyword_rank"],
        row["edge_rank"],
        row["centrality_rank"],
    ]

    ranks = [
        rank
        for rank in ranks
        if rank is not None
    ]

    if not ranks:
        return 0

    return (
        max(ranks)
        - min(ranks)
    )


# =========================================================
# 8. Top-N 합의 개수
#
# 예:
# BGE Top10
# Keyword Top10
# Edge Top10
# Centrality Top10
#
# 중 몇 개 지표가 이 기업을 Top10으로 보는가?
#
# 아직 가중치 아님.
# =========================================================

def count_top_n_agreement(
    row,
    n=10
):

    ranks = [
        row["bge_rank"],
        row["keyword_rank"],
        row["edge_rank"],
        row["centrality_rank"],
    ]

    return sum(
        1
        for rank in ranks
        if (
            rank is not None
            and rank <= n
        )
    )


# =========================================================
# 9. 결과 합치기
# =========================================================

def merge_results(
    bge_map,
    network_map
):

    stock_codes = sorted(
        set(
            bge_map.keys()
        )
        &
        set(
            network_map.keys()
        )
    )

    rows = []

    total = len(
        stock_codes
    )

    for stock_code in stock_codes:

        bge = (
            bge_map[
                stock_code
            ]
        )

        network = (
            network_map[
                stock_code
            ]
        )

        row = {
            "company_name":
                bge[
                    "company_name"
                ],

            "stock_code":
                stock_code,

            # ---------------------------------------------
            # Raw Score
            # ---------------------------------------------

            "bge_score":
                bge[
                    "bge_score"
                ],

            "keyword_score":
                network[
                    "keyword_score"
                ],

            "edge_score":
                network[
                    "edge_score"
                ],

            "centrality_score":
                network[
                    "centrality_score"
                ],

            # ---------------------------------------------
            # Rank
            # ---------------------------------------------

            "bge_rank":
                bge[
                    "bge_rank"
                ],

            "keyword_rank":
                network[
                    "keyword_rank"
                ],

            "edge_rank":
                network[
                    "edge_rank"
                ],

            "centrality_rank":
                network[
                    "centrality_rank"
                ],

            # ---------------------------------------------
            # Evidence
            # ---------------------------------------------

            "node_match_count":
                network[
                    "node_match_count"
                ],

            "edge_match_count":
                network[
                    "edge_match_count"
                ],
        }

        # ---------------------------------------------
        # Percentile
        # ---------------------------------------------

        row[
            "bge_percentile"
        ] = rank_to_percentile(
            row[
                "bge_rank"
            ],
            total
        )

        row[
            "keyword_percentile"
        ] = rank_to_percentile(
            row[
                "keyword_rank"
            ],
            total
        )

        row[
            "edge_percentile"
        ] = rank_to_percentile(
            row[
                "edge_rank"
            ],
            total
        )

        row[
            "centrality_percentile"
        ] = rank_to_percentile(
            row[
                "centrality_rank"
            ],
            total
        )

        # ---------------------------------------------
        # 단순 평균 percentile
        #
        # 이것은 최종 Late Fusion 점수가 아니다.
        # 오직 비교용.
        # ---------------------------------------------

        row[
            "mean_percentile"
        ] = float(
            mean(
                [
                    row[
                        "bge_percentile"
                    ],
                    row[
                        "keyword_percentile"
                    ],
                    row[
                        "edge_percentile"
                    ],
                    row[
                        "centrality_percentile"
                    ],
                ]
            )
        )

        row[
            "rank_spread"
        ] = calculate_rank_spread(
            row
        )

        row[
            "top5_agreement"
        ] = count_top_n_agreement(
            row,
            5
        )

        row[
            "top10_agreement"
        ] = count_top_n_agreement(
            row,
            10
        )

        rows.append(
            row
        )

    return rows


# =========================================================
# 10. CSV 저장
# =========================================================

def save_csv(
    path,
    rows
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if not rows:
        return

    fieldnames = [
        "company_name",
        "stock_code",

        "bge_score",
        "keyword_score",
        "edge_score",
        "centrality_score",

        "bge_rank",
        "keyword_rank",
        "edge_rank",
        "centrality_rank",

        "bge_percentile",
        "keyword_percentile",
        "edge_percentile",
        "centrality_percentile",

        "mean_percentile",

        "rank_spread",
        "top5_agreement",
        "top10_agreement",

        "node_match_count",
        "edge_match_count",
    ]

    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


# =========================================================
# 11. 터미널 출력
# =========================================================

def print_consensus_ranking(
    rows
):

    ranked = sorted(
        rows,
        key=lambda row: (
            row[
                "top10_agreement"
            ],
            row[
                "top5_agreement"
            ],
            row[
                "mean_percentile"
            ],
        ),
        reverse=True
    )

    print()
    print(
        "=" * 120
    )

    print(
        "Cross-Signal Agreement"
    )

    print(
        "=" * 120
    )

    print(
        f"{'Rank':<5}"
        f"{'Company':<20}"
        f"{'BGE':>6}"
        f"{'Key':>6}"
        f"{'Edge':>6}"
        f"{'Cent':>6}"
        f"{'Top5':>7}"
        f"{'Top10':>8}"
        f"{'Spread':>8}"
        f"{'MeanPct':>10}"
    )

    print(
        "-" * 120
    )

    for rank, row in enumerate(
        ranked[
            :TOP_N
        ],
        start=1
    ):

        print(
            f"{rank:<5}"
            f"{row['company_name']:<20}"
            f"{row['bge_rank']:>6}"
            f"{row['keyword_rank']:>6}"
            f"{row['edge_rank']:>6}"
            f"{row['centrality_rank']:>6}"
            f"{row['top5_agreement']:>7}"
            f"{row['top10_agreement']:>8}"
            f"{row['rank_spread']:>8}"
            f"{row['mean_percentile']:>10.4f}"
        )


# =========================================================
# 12. 가장 의견이 갈린 기업
# =========================================================

def print_disagreement(
    rows
):

    ranked = sorted(
        rows,
        key=lambda row:
            row[
                "rank_spread"
            ],
        reverse=True
    )

    print()
    print(
        "=" * 120
    )

    print(
        "Largest Rank Disagreement"
    )

    print(
        "=" * 120
    )

    for rank, row in enumerate(
        ranked[
            :15
        ],
        start=1
    ):

        print(
            f"#{rank:>2} "
            f"{row['company_name']:<20} | "
            f"BGE={row['bge_rank']:>2} "
            f"Keyword={row['keyword_rank']:>2} "
            f"Edge={row['edge_rank']:>2} "
            f"Centrality={row['centrality_rank']:>2} | "
            f"spread={row['rank_spread']}"
        )


# =========================================================
# 13. Main
# =========================================================

def main():

    print()
    print(
        "=" * 120
    )

    print(
        "PeerProof - Similarity Signal Comparison"
    )

    print(
        "=" * 120
    )

    bge_map = (
        load_bge_results()
    )

    network_map = (
        load_network_results()
    )

    rows = merge_results(
        bge_map,
        network_map
    )

    print(
        f"Matched Companies: "
        f"{len(rows)}"
    )

    print_consensus_ranking(
        rows
    )

    print_disagreement(
        rows
    )

    # -----------------------------------------------------
    # JSON
    # -----------------------------------------------------

    output = {
        "note":
            (
                "This file compares BGE, Keyword, Edge, "
                "and Centrality signals. "
                "mean_percentile is diagnostic only "
                "and is NOT the final Late Fusion score."
            ),

        "company_count":
            len(
                rows
            ),

        "results":
            rows,
    }

    save_json(
        OUTPUT_JSON,
        output
    )

    # -----------------------------------------------------
    # CSV
    # -----------------------------------------------------

    save_csv(
        OUTPUT_CSV,
        rows
    )

    print()
    print(
        "=" * 120
    )

    print(
        f"JSON 저장: {OUTPUT_JSON}"
    )

    print(
        f"CSV 저장 : {OUTPUT_CSV}"
    )

    print(
        "=" * 120
    )


if __name__ == "__main__":
    main()
