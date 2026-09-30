import json
from pathlib import Path
from statistics import mean

import numpy as np
from FlagEmbedding import BGEM3FlagModel


# =========================================================
# 1. Path
# =========================================================

PROJECT_ROOT = Path(
    "experiments/pilot_ipo"
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

BGE_PATH = (
    PROCESSED_DIR
    / "bge_similarity.json"
)

NETWORK_PATH = (
    PROCESSED_DIR
    / "language_network_similarity.json"
)

SIGNAL_COMPARE_PATH = (
    PROCESSED_DIR
    / "similarity_signal_comparison.json"
)

CANDIDATE_PROFILES_PATH = (
    PROCESSED_DIR
    / "candidate_profiles"
    / "profiles.json"
)

TARGET_COMPANIES_DIR = (
    PROCESSED_DIR
    / "companies"
)

OUTPUT_TXT = (
    PROJECT_ROOT
    / "outputs"
    / "12b_signal_disagreement_inspection.txt"
)

OUTPUT_JSON = (
    PROCESSED_DIR
    / "signal_disagreement_inspection.json"
)


# =========================================================
# 2. Config
# =========================================================

BGE_MODEL_NAME = (
    "BAAI/bge-m3"
)

BGE_BATCH_SIZE = 8

BGE_MAX_LENGTH = 2048


SELECTED_COMPANIES = [
    "뷰티스킨",
    "한국콜마",
    "애경산업",
    "펌텍코리아",
    "본느",
    "클리오",
    "아우딘퓨쳐스",
    "제이시스메디칼",
    "클래시스",
]


TOP_BGE_PAIRS = 5

TOP_NODE_MATCHES = 5

TOP_EDGE_MATCHES = 5


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
# 4. Target Profile
# =========================================================

def find_target_profile():

    paths = list(
        TARGET_COMPANIES_DIR.glob(
            "*/business_profile.json"
        )
    )

    for path in paths:

        data = load_json(
            path
        )

        company_name = (
            data
            .get(
                "company",
                {}
            )
            .get(
                "company_name"
            )
        )

        if company_name == "에이피알":

            return data

    raise RuntimeError(
        "에이피알 business_profile.json을 "
        "찾지 못했습니다."
    )


# =========================================================
# 5. Core Evidence
# =========================================================

def get_core_evidence(
    profile
):

    business_profile = (
        profile.get(
            "business_profile",
            {}
        )
    )

    core_evidence = (
        business_profile.get(
            "core_evidence",
            []
        )
    )

    results = []

    for item in core_evidence:

        text = (
            item.get(
                "text",
                ""
            ).strip()
        )

        if not text:
            continue

        results.append(
            {
                "text":
                    text,

                "categories":
                    item.get(
                        "categories",
                        []
                    ),

                "relevance_score":
                    item.get(
                        "relevance_score",
                        0
                    ),
            }
        )

    return results


# =========================================================
# 6. Candidate Profile Map
# =========================================================

def load_candidate_profiles():

    data = load_json(
        CANDIDATE_PROFILES_PATH
    )

    profiles = data.get(
        "profiles",
        []
    )

    result = {}

    for profile in profiles:

        company = (
            profile.get(
                "company",
                {}
            )
        )

        company_name = (
            company.get(
                "company_name"
            )
        )

        if company_name:

            result[
                company_name
            ] = profile

    return result


# =========================================================
# 7. Result Map
# =========================================================

def make_company_map(
    results
):

    output = {}

    for item in results:

        company_name = (
            item.get(
                "company_name"
            )
        )

        if company_name:

            output[
                company_name
            ] = item

    return output


# =========================================================
# 8. BGE Embedding
# =========================================================

def encode_texts(
    model,
    texts
):

    if not texts:

        return np.empty(
            (0, 0),
            dtype=np.float32
        )

    result = model.encode(
        texts,
        batch_size=
            BGE_BATCH_SIZE,
        max_length=
            BGE_MAX_LENGTH,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False
    )

    vectors = np.asarray(
        result[
            "dense_vecs"
        ],
        dtype=np.float32
    )

    # -----------------------------------------------------
    # cosine similarity를 위해 L2 normalize
    # -----------------------------------------------------

    norms = np.linalg.norm(
        vectors,
        axis=1,
        keepdims=True
    )

    norms[
        norms == 0
    ] = 1.0

    vectors = (
        vectors
        / norms
    )

    return vectors


# =========================================================
# 9. BGE Sentence Pair
#
# APR core sentence
# vs
# Candidate core sentence
#
# global cosine matrix를 만든 뒤
# 같은 sentence가 반복 사용되지 않게
# greedy one-to-one 방식으로 Top pair 선택
# =========================================================

def find_top_bge_pairs(
    target_evidence,
    candidate_evidence,
    target_vectors,
    candidate_vectors,
    top_n=5
):

    if (
        len(target_vectors) == 0
        or len(candidate_vectors) == 0
    ):

        return []

    similarity_matrix = (
        target_vectors
        @ candidate_vectors.T
    )

    pairs = []

    for target_index in range(
        similarity_matrix.shape[0]
    ):

        for candidate_index in range(
            similarity_matrix.shape[1]
        ):

            pairs.append(
                (
                    float(
                        similarity_matrix[
                            target_index,
                            candidate_index
                        ]
                    ),
                    target_index,
                    candidate_index,
                )
            )

    pairs.sort(
        key=lambda item:
            item[0],
        reverse=True
    )

    selected = []

    used_target = set()

    used_candidate = set()

    for (
        similarity,
        target_index,
        candidate_index
    ) in pairs:

        if target_index in used_target:
            continue

        if candidate_index in used_candidate:
            continue

        used_target.add(
            target_index
        )

        used_candidate.add(
            candidate_index
        )

        selected.append(
            {
                "similarity":
                    similarity,

                "target":
                    target_evidence[
                        target_index
                    ],

                "candidate":
                    candidate_evidence[
                        candidate_index
                    ],
            }
        )

        if len(
            selected
        ) >= top_n:

            break

    return selected


# =========================================================
# 10. Network 평균 Rank
# =========================================================

def calculate_network_rank_average(
    signal_item
):

    ranks = [
        signal_item.get(
            "keyword_rank"
        ),
        signal_item.get(
            "edge_rank"
        ),
        signal_item.get(
            "centrality_rank"
        ),
    ]

    ranks = [
        rank
        for rank in ranks
        if rank is not None
    ]

    if not ranks:
        return None

    return float(
        mean(
            ranks
        )
    )


# =========================================================
# 11. BGE vs Network Gap
#
# 양수:
# Network 평균 rank가 BGE보다 더 좋음
#
# 음수:
# BGE rank가 Network 평균보다 더 좋음
#
# 예)
#
# BGE 2
# Network 평균 25
#
# gap = 2 - 25 = -23
#
# → BGE 쪽이 훨씬 강함
#
#
# BGE 30
# Network 평균 3
#
# gap = 30 - 3 = +27
#
# → Network 쪽이 훨씬 강함
# =========================================================

def calculate_bge_network_gap(
    signal_item
):

    bge_rank = (
        signal_item.get(
            "bge_rank"
        )
    )

    network_average = (
        calculate_network_rank_average(
            signal_item
        )
    )

    if (
        bge_rank is None
        or network_average is None
    ):

        return None

    return float(
        bge_rank
        - network_average
    )


# =========================================================
# 12. Network Detail
# =========================================================

def get_network_details(
    network_item
):

    node_matches = sorted(
        network_item.get(
            "semantic_node_matches",
            []
        ),
        key=lambda item:
            item.get(
                "similarity",
                0.0
            ),
        reverse=True
    )

    edge_matches = sorted(
        network_item.get(
            "semantic_edge_matches",
            []
        ),
        key=lambda item:
            item.get(
                "semantic_similarity",
                0.0
            ),
        reverse=True
    )

    return {
        "node_matches":
            node_matches[
                :TOP_NODE_MATCHES
            ],

        "edge_matches":
            edge_matches[
                :TOP_EDGE_MATCHES
            ],
    }


# =========================================================
# 13. TXT 생성
# =========================================================

def build_text_report(
    reports
):

    lines = []

    def add(text=""):
        lines.append(
            str(
                text
            )
        )

    add(
        "=" * 120
    )

    add(
        "PeerProof - Signal Disagreement Inspection"
    )

    add(
        "=" * 120
    )

    add()

    add(
        "해석 기준"
    )

    add(
        "-" * 120
    )

    add(
        "BGE       : 전체 문장 의미 유사성"
    )

    add(
        "Keyword   : 핵심 개념 유사성"
    )

    add(
        "Edge      : 핵심 개념 관계 유사성"
    )

    add(
        "Centrality: 핵심 개념 중심 구조 유사성"
    )

    add()

    add(
        "BGE-Network Gap:"
    )

    add(
        "  음수 -> BGE 순위가 상대적으로 더 높음"
    )

    add(
        "  양수 -> Network 순위가 상대적으로 더 높음"
    )

    add()


    for report in reports:

        add()
        add(
            "#" * 120
        )

        add(
            report[
                "company_name"
            ]
        )

        add(
            "#" * 120
        )

        add()

        add(
            "[1. Rank Summary]"
        )

        add(
            "-" * 120
        )

        add(
            f"BGE Rank        : "
            f"{report['bge_rank']}"
        )

        add(
            f"Keyword Rank    : "
            f"{report['keyword_rank']}"
        )

        add(
            f"Edge Rank       : "
            f"{report['edge_rank']}"
        )

        add(
            f"Centrality Rank : "
            f"{report['centrality_rank']}"
        )

        add()

        add(
            f"Network Avg Rank: "
            f"{report['network_rank_average']:.2f}"
        )

        add(
            f"BGE-Network Gap : "
            f"{report['bge_network_gap']:.2f}"
        )

        add(
            f"Rank Spread     : "
            f"{report['rank_spread']}"
        )

        add(
            f"Top10 Agreement : "
            f"{report['top10_agreement']}/4"
        )

        add()

        add(
            "[2. Raw Scores]"
        )

        add(
            "-" * 120
        )

        add(
            f"BGE        : "
            f"{report['bge_score']:.4f}"
        )

        add(
            f"Keyword    : "
            f"{report['keyword_score']:.4f}"
        )

        add(
            f"Edge       : "
            f"{report['edge_score']:.4f}"
        )

        add(
            f"Centrality : "
            f"{report['centrality_score']:.4f}"
        )


        # =================================================
        # BGE
        # =================================================

        add()
        add(
            "[3. BGE Top Sentence Matches]"
        )

        add(
            "-" * 120
        )

        for index, pair in enumerate(
            report[
                "bge_sentence_matches"
            ],
            start=1
        ):

            add(
                f"{index}. "
                f"similarity="
                f"{pair['similarity']:.4f}"
            )

            add(
                "APR:"
            )

            add(
                pair[
                    "target"
                ][
                    "text"
                ]
            )

            add(
                "APR categories: "
                f"{pair['target'].get('categories', [])}"
            )

            add()

            add(
                "Candidate:"
            )

            add(
                pair[
                    "candidate"
                ][
                    "text"
                ]
            )

            add(
                "Candidate categories: "
                f"{pair['candidate'].get('categories', [])}"
            )

            add()


        # =================================================
        # Node
        # =================================================

        add(
            "[4. Semantic Node Matches]"
        )

        add(
            "-" * 120
        )

        for index, item in enumerate(
            report[
                "node_matches"
            ],
            start=1
        ):

            add(
                f"{index}. "
                f"APR: "
                f"{item.get('target_keyword')}"
            )

            add(
                f"   Candidate: "
                f"{item.get('candidate_keyword')}"
            )

            add(
                f"   similarity="
                f"{item.get('similarity', 0.0):.4f}"
            )

            add()


        # =================================================
        # Edge
        # =================================================

        add(
            "[5. Semantic Edge Matches]"
        )

        add(
            "-" * 120
        )

        for index, item in enumerate(
            report[
                "edge_matches"
            ],
            start=1
        ):

            target_edge = (
                item.get(
                    "target_edge",
                    []
                )
            )

            candidate_edge = (
                item.get(
                    "candidate_edge",
                    []
                )
            )

            add(
                f"{index}. "
                f"APR: "
                f"{' <-> '.join(target_edge)}"
            )

            add(
                f"   Candidate: "
                f"{' <-> '.join(candidate_edge)}"
            )

            add(
                f"   similarity="
                f"{item.get('semantic_similarity', 0.0):.4f}"
            )

            add()


    return "\n".join(
        lines
    )


# =========================================================
# 14. Main
# =========================================================

def main():

    print()
    print(
        "=" * 120
    )

    print(
        "PeerProof - Signal Disagreement Inspection"
    )

    print(
        "=" * 120
    )


    # =====================================================
    # Load Result
    # =====================================================

    bge_data = load_json(
        BGE_PATH
    )

    network_data = load_json(
        NETWORK_PATH
    )

    signal_data = load_json(
        SIGNAL_COMPARE_PATH
    )


    bge_map = make_company_map(
        bge_data.get(
            "results",
            []
        )
    )

    network_map = make_company_map(
        network_data.get(
            "results",
            []
        )
    )

    signal_map = make_company_map(
        signal_data.get(
            "results",
            []
        )
    )


    # =====================================================
    # Profile
    # =====================================================

    target_profile = (
        find_target_profile()
    )

    candidate_profiles = (
        load_candidate_profiles()
    )


    target_evidence = (
        get_core_evidence(
            target_profile
        )
    )

    target_texts = [
        item[
            "text"
        ]
        for item
        in target_evidence
    ]


    # =====================================================
    # BGE Model
    # =====================================================

    print()

    print(
        "BGE-M3 모델 로딩..."
    )

    bge_model = (
        BGEM3FlagModel(
            BGE_MODEL_NAME,
            use_fp16=True
        )
    )

    print(
        "BGE-M3 모델 로딩 완료"
    )


    print()

    print(
        "APR core_evidence embedding..."
    )

    target_vectors = (
        encode_texts(
            bge_model,
            target_texts
        )
    )

    print(
        f"APR vector shape: "
        f"{target_vectors.shape}"
    )


    # =====================================================
    # Selected Company
    # =====================================================

    reports = []


    for index, company_name in enumerate(
        SELECTED_COMPANIES,
        start=1
    ):

        print()

        print(
            f"[{index}/{len(SELECTED_COMPANIES)}] "
            f"{company_name}"
        )


        if company_name not in signal_map:

            print(
                "  Signal result 없음"
            )

            continue


        if company_name not in network_map:

            print(
                "  Network result 없음"
            )

            continue


        if company_name not in candidate_profiles:

            print(
                "  Candidate profile 없음"
            )

            continue


        signal_item = (
            signal_map[
                company_name
            ]
        )

        network_item = (
            network_map[
                company_name
            ]
        )

        candidate_profile = (
            candidate_profiles[
                company_name
            ]
        )


        candidate_evidence = (
            get_core_evidence(
                candidate_profile
            )
        )

        candidate_texts = [
            item[
                "text"
            ]
            for item
            in candidate_evidence
        ]


        candidate_vectors = (
            encode_texts(
                bge_model,
                candidate_texts
            )
        )


        bge_pairs = (
            find_top_bge_pairs(
                target_evidence,
                candidate_evidence,
                target_vectors,
                candidate_vectors,
                TOP_BGE_PAIRS
            )
        )


        network_details = (
            get_network_details(
                network_item
            )
        )


        network_average = (
            calculate_network_rank_average(
                signal_item
            )
        )


        bge_network_gap = (
            calculate_bge_network_gap(
                signal_item
            )
        )


        report = {
            "company_name":
                company_name,

            "stock_code":
                signal_item.get(
                    "stock_code"
                ),

            # ---------------------------------------------
            # Rank
            # ---------------------------------------------

            "bge_rank":
                signal_item.get(
                    "bge_rank"
                ),

            "keyword_rank":
                signal_item.get(
                    "keyword_rank"
                ),

            "edge_rank":
                signal_item.get(
                    "edge_rank"
                ),

            "centrality_rank":
                signal_item.get(
                    "centrality_rank"
                ),

            "network_rank_average":
                network_average,

            "bge_network_gap":
                bge_network_gap,

            "rank_spread":
                signal_item.get(
                    "rank_spread"
                ),

            "top5_agreement":
                signal_item.get(
                    "top5_agreement"
                ),

            "top10_agreement":
                signal_item.get(
                    "top10_agreement"
                ),

            # ---------------------------------------------
            # Score
            # ---------------------------------------------

            "bge_score":
                signal_item.get(
                    "bge_score"
                ),

            "keyword_score":
                signal_item.get(
                    "keyword_score"
                ),

            "edge_score":
                signal_item.get(
                    "edge_score"
                ),

            "centrality_score":
                signal_item.get(
                    "centrality_score"
                ),

            # ---------------------------------------------
            # Evidence Count
            # ---------------------------------------------

            "target_core_count":
                len(
                    target_evidence
                ),

            "candidate_core_count":
                len(
                    candidate_evidence
                ),

            "node_match_count":
                signal_item.get(
                    "node_match_count"
                ),

            "edge_match_count":
                signal_item.get(
                    "edge_match_count"
                ),

            # ---------------------------------------------
            # Detail
            # ---------------------------------------------

            "bge_sentence_matches":
                bge_pairs,

            "node_matches":
                network_details[
                    "node_matches"
                ],

            "edge_matches":
                network_details[
                    "edge_matches"
                ],
        }


        reports.append(
            report
        )


        print(
            f"  BGE={report['bge_rank']} "
            f"Keyword={report['keyword_rank']} "
            f"Edge={report['edge_rank']} "
            f"Centrality={report['centrality_rank']} "
            f"Gap={report['bge_network_gap']:.2f}"
        )


    # =====================================================
    # Save JSON
    # =====================================================

    output = {
        "target_company":
            "에이피알",

        "selected_company_count":
            len(
                reports
            ),

        "definition": {
            "bge":
                "sentence-level semantic similarity",

            "keyword":
                "semantic keyword overlap",

            "edge":
                "semantic relationship similarity",

            "centrality":
                "filtered weighted graph centrality similarity",

            "bge_network_gap":
                (
                    "BGE rank - average network rank. "
                    "Negative means BGE is relatively stronger. "
                    "Positive means network is relatively stronger."
                ),
        },

        "results":
            reports,
    }


    save_json(
        OUTPUT_JSON,
        output
    )


    # =====================================================
    # TXT
    # =====================================================

    text_report = (
        build_text_report(
            reports
        )
    )


    OUTPUT_TXT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_TXT,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            text_report
        )


    print()
    print(
        "=" * 120
    )

    print(
        "Inspection 완료"
    )

    print(
        f"TXT : {OUTPUT_TXT}"
    )

    print(
        f"JSON: {OUTPUT_JSON}"
    )

    print(
        "=" * 120
    )


if __name__ == "__main__":
    main()
