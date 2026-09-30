import json
import re
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer


# =========================================================
# 1. Path
# =========================================================

PROJECT_ROOT = Path("experiments/pilot_ipo")

TARGET_COMPANIES_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "companies"
)

CANDIDATE_PROFILES_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "candidate_profiles"
    / "profiles.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "language_network_similarity.json"
)


# =========================================================
# 2. Model / Experiment Config
# =========================================================

KEYWORD_MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

# 한 core 문장에서 추출할 keyword 수
KEYWORDS_PER_SENTENCE = 4

# unigram + bigram
NGRAM_RANGE = (1, 2)

# KeyBERT MMR 다양성
MMR_DIVERSITY = 0.5

# 한 기업에서 최종적으로 유지할 최대 keyword/node 수
MAX_KEYWORDS_PER_COMPANY = 60

# 너무 낮은 KeyBERT 후보 제거
MIN_KEYBERT_SCORE = 0.35

# ---------------------------------------------------------
# Semantic Node Alignment
#
# 두 keyword의 cosine similarity가 이 값 이상이면
# 의미적으로 같은 개념의 후보로 인정
#
# 정답값이 아니라 파일럿 실험 파라미터
# ---------------------------------------------------------

NODE_MATCH_THRESHOLD = 0.75


# ---------------------------------------------------------
# Semantic Edge Alignment
#
# 두 edge의 양 끝 Node가 의미적으로 유사한 경우
# 같은 관계로 인정
#
# Node보다 조금 완화된 threshold
# ---------------------------------------------------------

EDGE_MATCH_THRESHOLD = 0.70


# =========================================================
# 3. 일반적인 언어 노이즈
#
# 화장품/D2C/브랜드 같은 도메인 vocabulary가 아님.
#
# 기업 사업 특성과 관계없는 일반적 표현만 제거.
# =========================================================

GENERIC_STOPWORDS = {
    "당사",
    "자사",
    "회사",
    "기업",
    "있습니다",
    "있으며",
    "입니다",
    "합니다",
    "하였습니다",
    "되었습니다",
    "통해",
    "위해",
    "대한",
    "경우",
    "관련",
    "등",
    "및",
    "수",
    "것",
}


GENERIC_NOISE_PHRASES = {
    "부정적인 영향",
    "긍정적인 영향",
    "영향 미칠",
    "영향을 미칠",
    "계획입니다",
    "예정입니다",
    "있습니다",
    "하고 있습니다",
    "할 수 있습니다",
    "증가할 수",
    "감소할 수",
}


# =========================================================
# 4. JSON
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


def save_json(path, data):

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
# 5. Target Profile
# =========================================================

def find_target_profile():

    matches = list(
        TARGET_COMPANIES_DIR.glob(
            "*/business_profile.json"
        )
    )

    if not matches:
        raise FileNotFoundError(
            "Target business_profile.json이 없습니다."
        )

    if len(matches) == 1:
        return matches[0]

    for path in matches:

        data = load_json(path)

        company_name = (
            data
            .get("company", {})
            .get("company_name")
        )

        if company_name == "에이피알":
            return path

    raise RuntimeError(
        "에이피알 business_profile.json을 "
        "찾지 못했습니다."
    )


# =========================================================
# 6. Core Evidence
# =========================================================

def extract_core_sentences(profile):

    business_profile = profile.get(
        "business_profile",
        {}
    )

    core_evidence = business_profile.get(
        "core_evidence",
        []
    )

    sentences = []

    for item in core_evidence:

        text = item.get(
            "text",
            ""
        ).strip()

        if text:
            sentences.append(text)

    return sentences


# =========================================================
# 7. Keyword Normalize
#
# v2에서 조사 제거를 직접 하면서
#
# 증가하는 -> 증가하
# 판매하는 -> 판매하
#
# 같은 형태가 만들어지는 문제가 있었음.
#
# v3에서는 공격적인 한국어 suffix 제거를 하지 않음.
# =========================================================

def normalize_keyword(keyword):

    keyword = (
        keyword
        .lower()
        .strip()
    )

    # 특수문자 정리
    keyword = re.sub(
        r"[^\w가-힣a-zA-Z\s\-]",
        " ",
        keyword
    )

    keyword = re.sub(
        r"\s+",
        " ",
        keyword
    ).strip()

    if not keyword:
        return ""

    tokens = []

    for token in keyword.split():

        # stopword 자체인 token만 제거
        if token in GENERIC_STOPWORDS:
            continue

        # 숫자만 있는 token 제거
        if re.fullmatch(
            r"\d+(\.\d+)?",
            token
        ):
            continue

        tokens.append(token)

    keyword = " ".join(tokens).strip()

    if len(keyword) < 2:
        return ""

    return keyword


# =========================================================
# 8. Keyword Noise Filter
# =========================================================

def is_noisy_keyword(keyword, score):

    if not keyword:
        return True

    # KeyBERT relevance가 너무 낮으면 제거
    if score < MIN_KEYBERT_SCORE:
        return True

    lowered = keyword.lower()

    # 일반적인 boilerplate 표현 제거
    for phrase in GENERIC_NOISE_PHRASES:

        if phrase in lowered:
            return True

    # 숫자로만 구성
    if re.fullmatch(
        r"[\d\s.%]+",
        lowered
    ):
        return True

    # 날짜/연도 정보만 있는 짧은 표현
    if (
        re.search(
            r"\d{4}년|\d+월|\d+일",
            lowered
        )
        and len(lowered.split()) <= 2
    ):
        return True

    # 지나치게 짧은 표현
    if len(lowered.replace(" ", "")) < 2:
        return True

    return False


# =========================================================
# 9. Sentence-level KeyBERT
#
# 문서 전체에서 Top-N을 한 번 뽑지 않고,
# 각 core sentence별로 keyword를 추출한다.
#
# 이유:
# Edge = 같은 문장 안에서 등장한 핵심 개념 관계
# =========================================================

def extract_sentence_keywords(
    keyword_model,
    sentences
):

    if not sentences:
        return []

    raw_results = (
        keyword_model.extract_keywords(
            sentences,
            keyphrase_ngram_range=NGRAM_RANGE,
            stop_words=None,
            top_n=KEYWORDS_PER_SENTENCE,
            use_mmr=True,
            diversity=MMR_DIVERSITY
        )
    )

    sentence_keywords = []

    for sentence, keyword_list in zip(
        sentences,
        raw_results
    ):

        cleaned = []
        seen = set()

        for keyword, score in keyword_list:

            score = float(score)

            normalized = normalize_keyword(
                keyword
            )

            if is_noisy_keyword(
                normalized,
                score
            ):
                continue

            if normalized in seen:
                continue

            seen.add(normalized)

            cleaned.append(
                {
                    "keyword": normalized,
                    "score": score,
                }
            )

        sentence_keywords.append(
            {
                "sentence": sentence,
                "keywords": cleaned,
            }
        )

    return sentence_keywords


# =========================================================
# 10. Company Keyword Aggregate
#
# frequency:
# 몇 개 core 문장에서 등장했는가
#
# mean_keybert_score:
# 해당 keyword의 평균 KeyBERT relevance
#
# importance:
# frequency * mean score
#
# 사람이 임의로 부여한 중요도 가중치가 아니라
# 데이터 기반 값.
# =========================================================

def aggregate_keywords(
    sentence_keywords
):

    accumulator = {}

    for item in sentence_keywords:

        for keyword_item in item["keywords"]:

            keyword = (
                keyword_item["keyword"]
            )

            score = (
                keyword_item["score"]
            )

            if keyword not in accumulator:

                accumulator[keyword] = {
                    "frequency": 0,
                    "scores": [],
                }

            accumulator[
                keyword
            ][
                "frequency"
            ] += 1

            accumulator[
                keyword
            ][
                "scores"
            ].append(
                score
            )

    results = []

    for keyword, data in accumulator.items():

        frequency = data["frequency"]

        mean_score = float(
            np.mean(
                data["scores"]
            )
        )

        importance = float(
            frequency
            * mean_score
        )

        results.append(
            {
                "keyword": keyword,
                "frequency": frequency,
                "mean_keybert_score": mean_score,
                "importance": importance,
            }
        )

    results.sort(
        key=lambda item: (
            item["importance"],
            item["frequency"],
            item["mean_keybert_score"],
        ),
        reverse=True
    )

    return results[
        :MAX_KEYWORDS_PER_COMPANY
    ]


# =========================================================
# 11. Graph
#
# Node:
# 자유롭게 추출된 keyword
#
# Edge:
# 동일 core sentence에서 함께 추출된 keyword pair
#
# Edge weight:
# 그 keyword pair의 동시출현 문장 수
# =========================================================

def build_keyword_graph(
    sentence_keywords,
    selected_keywords
):

    graph = nx.Graph()

    selected_map = {
        item["keyword"]: item
        for item in selected_keywords
    }

    selected_set = set(
        selected_map.keys()
    )

    # Node
    for keyword, data in selected_map.items():

        graph.add_node(
            keyword,
            frequency=data["frequency"],
            importance=data["importance"],
            keybert_score=data[
                "mean_keybert_score"
            ]
        )

    # Edge
    for sentence_item in sentence_keywords:

        found_keywords = []

        for keyword_item in sentence_item[
            "keywords"
        ]:

            keyword = (
                keyword_item["keyword"]
            )

            if keyword in selected_set:
                found_keywords.append(
                    keyword
                )

        found_keywords = sorted(
            set(found_keywords)
        )

        for keyword_a, keyword_b in combinations(
            found_keywords,
            2
        ):

            if graph.has_edge(
                keyword_a,
                keyword_b
            ):

                graph[
                    keyword_a
                ][
                    keyword_b
                ][
                    "weight"
                ] += 1

            else:

                graph.add_edge(
                    keyword_a,
                    keyword_b,
                    weight=1
                )

    return graph


# =========================================================
# 12. Keyword Embedding
#
# BGE company embedding과 다름.
#
# 여기서는 keyword node 의미를 맞추기 위한
# 보조 도구로만 embedding을 사용.
# =========================================================

def embed_keywords(
    sentence_model,
    keywords
):

    if not keywords:

        return np.empty(
            (0, 0),
            dtype=np.float32
        )

    vectors = sentence_model.encode(
        keywords,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    return np.asarray(
        vectors,
        dtype=np.float32
    )


# =========================================================
# 13. Node Semantic Similarity Matrix
# =========================================================

def build_node_similarity_matrix(
    target_vectors,
    candidate_vectors
):

    if (
        len(target_vectors) == 0
        or len(candidate_vectors) == 0
    ):

        return np.empty(
            (
                len(target_vectors),
                len(candidate_vectors)
            ),
            dtype=np.float32
        )

    return (
        target_vectors
        @ candidate_vectors.T
    )


# =========================================================
# 14. Semantic Node Alignment
#
# 고정 vocabulary 사용 X
#
# 각 기업에서 자유롭게 뽑힌 keyword를
# 의미적으로 비교한다.
#
# one-to-one greedy matching
# =========================================================

def align_nodes(
    target_keywords,
    candidate_keywords,
    similarity_matrix
):

    if (
        len(target_keywords) == 0
        or len(candidate_keywords) == 0
    ):

        return [], {}

    pairs = []

    for target_index in range(
        similarity_matrix.shape[0]
    ):

        for candidate_index in range(
            similarity_matrix.shape[1]
        ):

            similarity = float(
                similarity_matrix[
                    target_index,
                    candidate_index
                ]
            )

            if (
                similarity
                >= NODE_MATCH_THRESHOLD
            ):

                pairs.append(
                    (
                        similarity,
                        target_index,
                        candidate_index
                    )
                )

    pairs.sort(
        key=lambda x: x[0],
        reverse=True
    )

    used_target = set()
    used_candidate = set()

    matches = []
    mapping = {}

    for (
        similarity,
        target_index,
        candidate_index
    ) in pairs:

        if target_index in used_target:
            continue

        if candidate_index in used_candidate:
            continue

        target_keyword = (
            target_keywords[
                target_index
            ]
        )

        candidate_keyword = (
            candidate_keywords[
                candidate_index
            ]
        )

        used_target.add(target_index)
        used_candidate.add(candidate_index)

        mapping[
            candidate_keyword
        ] = target_keyword

        matches.append(
            {
                "target_keyword":
                    target_keyword,

                "candidate_keyword":
                    candidate_keyword,

                "similarity":
                    similarity,
            }
        )

    return matches, mapping


# =========================================================
# 15. Semantic Keyword Jaccard
# =========================================================

def semantic_keyword_jaccard(
    target_graph,
    candidate_graph,
    matches
):

    target_count = (
        target_graph.number_of_nodes()
    )

    candidate_count = (
        candidate_graph.number_of_nodes()
    )

    matched_count = len(matches)

    union_count = (
        target_count
        + candidate_count
        - matched_count
    )

    if union_count == 0:
        return 0.0

    return float(
        matched_count
        / union_count
    )


# =========================================================
# 16. Candidate Graph Align
#
# Centrality 비교용.
#
# 매칭된 후보 keyword는 APR keyword 좌표로 정렬.
# =========================================================

def align_candidate_graph(
    candidate_graph,
    mapping
):

    aligned_graph = nx.Graph()

    for node, data in candidate_graph.nodes(
        data=True
    ):

        if node in mapping:
            aligned_node = mapping[node]
        else:
            aligned_node = (
                f"__candidate__::{node}"
            )

        if aligned_node not in aligned_graph:

            aligned_graph.add_node(
                aligned_node,
                **data
            )

    for (
        node_a,
        node_b,
        data
    ) in candidate_graph.edges(
        data=True
    ):

        aligned_a = mapping.get(
            node_a,
            f"__candidate__::{node_a}"
        )

        aligned_b = mapping.get(
            node_b,
            f"__candidate__::{node_b}"
        )

        if aligned_a == aligned_b:
            continue

        weight = float(
            data.get(
                "weight",
                1.0
            )
        )

        if aligned_graph.has_edge(
            aligned_a,
            aligned_b
        ):

            aligned_graph[
                aligned_a
            ][
                aligned_b
            ][
                "weight"
            ] += weight

        else:

            aligned_graph.add_edge(
                aligned_a,
                aligned_b,
                weight=weight
            )

    return aligned_graph


# =========================================================
# 17. Soft Semantic Edge Matching
#
# 핵심 수정 부분.
#
# 기존:
#
# APR
# A -- B
#
# 후보
# C -- D
#
# A==C, B==D 수준으로 맞아야 공통 edge
#
#
# v3:
#
# sim(A,C), sim(B,D)
# 또는
# sim(A,D), sim(B,C)
#
# 중 더 좋은 방향을 선택.
#
# 두 끝점이 모두 충분히 의미적으로 가까우면
# 비슷한 관계(edge)로 인정.
# =========================================================

def edge_semantic_similarity(
    target_edge,
    candidate_edge,
    target_index_map,
    candidate_index_map,
    similarity_matrix
):

    target_a, target_b = target_edge
    candidate_a, candidate_b = candidate_edge

    ta = target_index_map[target_a]
    tb = target_index_map[target_b]

    ca = candidate_index_map[candidate_a]
    cb = candidate_index_map[candidate_b]

    # 같은 방향
    direct = min(
        float(
            similarity_matrix[
                ta,
                ca
            ]
        ),
        float(
            similarity_matrix[
                tb,
                cb
            ]
        )
    )

    # 반대 방향
    reverse = min(
        float(
            similarity_matrix[
                ta,
                cb
            ]
        ),
        float(
            similarity_matrix[
                tb,
                ca
            ]
        )
    )

    return max(
        direct,
        reverse
    )


# =========================================================
# 18. Soft Weighted Edge Jaccard
#
# 완전 동일 edge 대신
# semantic edge를 one-to-one으로 matching.
#
# numerator:
# min(edge weight) * semantic similarity
#
# denominator:
# target edge weight 총합
# + candidate edge weight 총합
# - matched mass
# =========================================================

def soft_weighted_edge_jaccard(
    target_graph,
    candidate_graph,
    target_keywords,
    candidate_keywords,
    similarity_matrix
):

    if (
        target_graph.number_of_edges() == 0
        or candidate_graph.number_of_edges() == 0
    ):
        return 0.0, []

    target_index_map = {
        keyword: index
        for index, keyword
        in enumerate(target_keywords)
    }

    candidate_index_map = {
        keyword: index
        for index, keyword
        in enumerate(candidate_keywords)
    }

    target_edges = []

    for node_a, node_b, data in target_graph.edges(
        data=True
    ):

        target_edges.append(
            {
                "nodes": (
                    node_a,
                    node_b
                ),
                "weight": float(
                    data.get(
                        "weight",
                        1.0
                    )
                ),
            }
        )

    candidate_edges = []

    for node_a, node_b, data in candidate_graph.edges(
        data=True
    ):

        candidate_edges.append(
            {
                "nodes": (
                    node_a,
                    node_b
                ),
                "weight": float(
                    data.get(
                        "weight",
                        1.0
                    )
                ),
            }
        )

    candidates = []

    for target_edge_index, target_edge in enumerate(
        target_edges
    ):

        for candidate_edge_index, candidate_edge in enumerate(
            candidate_edges
        ):

            similarity = (
                edge_semantic_similarity(
                    target_edge[
                        "nodes"
                    ],
                    candidate_edge[
                        "nodes"
                    ],
                    target_index_map,
                    candidate_index_map,
                    similarity_matrix
                )
            )

            if (
                similarity
                >= EDGE_MATCH_THRESHOLD
            ):

                candidates.append(
                    (
                        similarity,
                        target_edge_index,
                        candidate_edge_index
                    )
                )

    candidates.sort(
        key=lambda item: item[0],
        reverse=True
    )

    used_target_edges = set()
    used_candidate_edges = set()

    matched_mass = 0.0
    edge_matches = []

    for (
        similarity,
        target_edge_index,
        candidate_edge_index
    ) in candidates:

        if (
            target_edge_index
            in used_target_edges
        ):
            continue

        if (
            candidate_edge_index
            in used_candidate_edges
        ):
            continue

        target_edge = (
            target_edges[
                target_edge_index
            ]
        )

        candidate_edge = (
            candidate_edges[
                candidate_edge_index
            ]
        )

        used_target_edges.add(
            target_edge_index
        )

        used_candidate_edges.add(
            candidate_edge_index
        )

        common_weight = min(
            target_edge["weight"],
            candidate_edge["weight"]
        )

        contribution = (
            common_weight
            * similarity
        )

        matched_mass += contribution

        edge_matches.append(
            {
                "target_edge": list(
                    target_edge["nodes"]
                ),

                "candidate_edge": list(
                    candidate_edge["nodes"]
                ),

                "semantic_similarity":
                    float(similarity),

                "target_weight":
                    target_edge["weight"],

                "candidate_weight":
                    candidate_edge["weight"],

                "matched_mass":
                    float(contribution),
            }
        )

    target_total_weight = sum(
        edge["weight"]
        for edge in target_edges
    )

    candidate_total_weight = sum(
        edge["weight"]
        for edge in candidate_edges
    )

    denominator = (
        target_total_weight
        + candidate_total_weight
        - matched_mass
    )

    if denominator <= 0:
        return 0.0, edge_matches

    score = float(
        matched_mass
        / denominator
    )

    edge_matches.sort(
        key=lambda item:
            item[
                "semantic_similarity"
            ],
        reverse=True
    )

    return (
        score,
        edge_matches
    )


# =========================================================
# 19. Weighted Degree Centrality
#
# Edge weight = co-occurrence frequency 반영
# =========================================================

def get_weighted_degree_centrality(
    graph
):

    node_count = (
        graph.number_of_nodes()
    )

    if node_count <= 1:

        return {
            node: 0.0
            for node in graph.nodes()
        }

    centrality = {}

    for node in graph.nodes():

        weighted_degree = float(
            graph.degree(
                node,
                weight="weight"
            )
        )

        centrality[node] = (
            weighted_degree
            / (
                node_count
                - 1
            )
        )

    return centrality


# =========================================================
# 20. Weighted Centrality Cosine
# =========================================================

def weighted_centrality_cosine(
    target_graph,
    aligned_candidate_graph
):

    all_nodes = sorted(
        set(
            target_graph.nodes()
        )
        |
        set(
            aligned_candidate_graph.nodes()
        )
    )

    if not all_nodes:
        return 0.0

    centrality_a = (
        get_weighted_degree_centrality(
            target_graph
        )
    )

    centrality_b = (
        get_weighted_degree_centrality(
            aligned_candidate_graph
        )
    )

    vector_a = np.array(
        [
            centrality_a.get(
                node,
                0.0
            )
            for node in all_nodes
        ],
        dtype=np.float32
    )

    vector_b = np.array(
        [
            centrality_b.get(
                node,
                0.0
            )
            for node in all_nodes
        ],
        dtype=np.float32
    )

    norm_a = np.linalg.norm(
        vector_a
    )

    norm_b = np.linalg.norm(
        vector_b
    )

    if (
        norm_a == 0
        or norm_b == 0
    ):
        return 0.0

    return float(
        np.dot(
            vector_a,
            vector_b
        )
        /
        (
            norm_a
            * norm_b
        )
    )


# =========================================================
# 21. Graph Summary
# =========================================================

def graph_summary(graph):

    node_count = (
        graph.number_of_nodes()
    )

    edge_count = (
        graph.number_of_edges()
    )

    if node_count > 1:

        density = float(
            nx.density(graph)
        )

        average_clustering = float(
            nx.average_clustering(
                graph,
                weight="weight"
            )
        )

    else:

        density = 0.0
        average_clustering = 0.0

    weighted_degree = sorted(
        [
            (
                node,
                float(
                    graph.degree(
                        node,
                        weight="weight"
                    )
                )
            )
            for node in graph.nodes()
        ],
        key=lambda x: x[1],
        reverse=True
    )

    top_central_keywords = [
        {
            "keyword": node,
            "weighted_degree": degree,
        }
        for node, degree
        in weighted_degree[:10]
    ]

    return {
        "node_count":
            node_count,

        "edge_count":
            edge_count,

        "density":
            density,

        "average_clustering":
            average_clustering,

        "top_central_keywords":
            top_central_keywords,
    }


# =========================================================
# 22. Ranking
# =========================================================

def add_rank(
    results,
    metric_name,
    rank_name
):

    ranked = sorted(
        results,
        key=lambda item:
            item[metric_name],
        reverse=True
    )

    for rank, item in enumerate(
        ranked,
        start=1
    ):

        item[
            rank_name
        ] = rank


def print_ranking(
    results,
    metric_name,
    title,
    top_n=15
):

    ranked = sorted(
        results,
        key=lambda item:
            item[metric_name],
        reverse=True
    )

    print()
    print("=" * 100)
    print(title)
    print("=" * 100)

    for rank, item in enumerate(
        ranked[:top_n],
        start=1
    ):

        print(
            f"#{rank:>2} "
            f"{item['company_name']:<20} "
            f"{item['stock_code']} | "
            f"{metric_name}="
            f"{item[metric_name]:.4f}"
        )


# =========================================================
# 23. Company Network
# =========================================================

def build_company_network(
    keyword_model,
    sentences
):

    sentence_keywords = (
        extract_sentence_keywords(
            keyword_model,
            sentences
        )
    )

    keywords = (
        aggregate_keywords(
            sentence_keywords
        )
    )

    graph = (
        build_keyword_graph(
            sentence_keywords,
            keywords
        )
    )

    return (
        sentence_keywords,
        keywords,
        graph
    )


# =========================================================
# 24. Main
# =========================================================

def main():

    print()
    print("=" * 100)
    print(
        "PeerProof - Language Network Similarity v3"
    )
    print("=" * 100)
    print()

    # -----------------------------------------------------
    # Model
    # -----------------------------------------------------

    print(
        "KeyBERT / Semantic Network 모델 로딩..."
    )

    sentence_model = (
        SentenceTransformer(
            KEYWORD_MODEL_NAME
        )
    )

    keyword_model = (
        KeyBERT(
            model=sentence_model
        )
    )

    print("모델 로딩 완료")
    print()

    # -----------------------------------------------------
    # Target
    # -----------------------------------------------------

    target_path = (
        find_target_profile()
    )

    target_profile = (
        load_json(
            target_path
        )
    )

    target_company = (
        target_profile["company"]
    )

    target_sentences = (
        extract_core_sentences(
            target_profile
        )
    )

    (
        target_sentence_keywords,
        target_keyword_data,
        target_graph
    ) = build_company_network(
        keyword_model,
        target_sentences
    )

    target_keywords = [
        item["keyword"]
        for item in target_keyword_data
    ]

    target_vectors = (
        embed_keywords(
            sentence_model,
            target_keywords
        )
    )

    print(
        f"Target Company : "
        f"{target_company['company_name']}"
    )

    print(
        f"Target Core    : "
        f"{len(target_sentences)}"
    )

    print(
        f"Target Nodes   : "
        f"{target_graph.number_of_nodes()}"
    )

    print(
        f"Target Edges   : "
        f"{target_graph.number_of_edges()}"
    )

    print()

    print("APR Top Keywords")
    print("-" * 100)

    for index, item in enumerate(
        target_keyword_data[:20],
        start=1
    ):

        print(
            f"{index:>2}. "
            f"{item['keyword']:<35} "
            f"freq={item['frequency']:>2} "
            f"score="
            f"{item['mean_keybert_score']:.4f}"
        )

    # -----------------------------------------------------
    # Candidates
    # -----------------------------------------------------

    candidate_data = (
        load_json(
            CANDIDATE_PROFILES_PATH
        )
    )

    candidates = (
        candidate_data.get(
            "profiles",
            []
        )
    )

    results = []

    total = len(candidates)

    print()
    print("=" * 100)
    print(
        "Candidate Language Networks"
    )
    print("=" * 100)

    for index, candidate in enumerate(
        candidates,
        start=1
    ):

        company = candidate.get(
            "company",
            {}
        )

        company_name = company.get(
            "company_name"
        )

        stock_code = company.get(
            "stock_code"
        )

        corp_code = company.get(
            "corp_code"
        )

        sentences = (
            extract_core_sentences(
                candidate
            )
        )

        if not sentences:
            continue

        (
            candidate_sentence_keywords,
            candidate_keyword_data,
            candidate_graph
        ) = build_company_network(
            keyword_model,
            sentences
        )

        candidate_keywords = [
            item["keyword"]
            for item
            in candidate_keyword_data
        ]

        candidate_vectors = (
            embed_keywords(
                sentence_model,
                candidate_keywords
            )
        )

        # ---------------------------------------------
        # Node similarity matrix
        # ---------------------------------------------

        similarity_matrix = (
            build_node_similarity_matrix(
                target_vectors,
                candidate_vectors
            )
        )

        # ---------------------------------------------
        # Semantic Node Alignment
        # ---------------------------------------------

        (
            node_matches,
            node_mapping
        ) = align_nodes(
            target_keywords,
            candidate_keywords,
            similarity_matrix
        )

        aligned_candidate_graph = (
            align_candidate_graph(
                candidate_graph,
                node_mapping
            )
        )

        # ---------------------------------------------
        # Keyword score
        # ---------------------------------------------

        keyword_score = (
            semantic_keyword_jaccard(
                target_graph,
                candidate_graph,
                node_matches
            )
        )

        # ---------------------------------------------
        # NEW: Semantic Edge score
        # ---------------------------------------------

        (
            edge_score,
            edge_matches
        ) = soft_weighted_edge_jaccard(
            target_graph,
            candidate_graph,
            target_keywords,
            candidate_keywords,
            similarity_matrix
        )

        # ---------------------------------------------
        # Centrality
        # ---------------------------------------------

        centrality_score = (
            weighted_centrality_cosine(
                target_graph,
                aligned_candidate_graph
            )
        )

        result = {

            "company_name":
                company_name,

            "stock_code":
                stock_code,

            "corp_code":
                corp_code,

            "core_evidence_count":
                len(sentences),

            "keyword_count":
                len(candidate_keywords),

            "semantic_node_match_count":
                len(node_matches),

            "semantic_node_matches":
                node_matches[:20],

            "semantic_edge_match_count":
                len(edge_matches),

            "semantic_edge_matches":
                edge_matches[:20],

            "keywords":
                candidate_keyword_data,

            "graph":
                graph_summary(
                    candidate_graph
                ),

            "semantic_keyword_jaccard":
                float(keyword_score),

            "soft_weighted_edge_jaccard":
                float(edge_score),

            "weighted_centrality_cosine":
                float(centrality_score),
        }

        results.append(result)

        print(
            f"[{index}/{total}] "
            f"{company_name:<20} | "
            f"nodes="
            f"{candidate_graph.number_of_nodes():>2} "
            f"edges="
            f"{candidate_graph.number_of_edges():>3} "
            f"node_match="
            f"{len(node_matches):>2} "
            f"edge_match="
            f"{len(edge_matches):>2} | "
            f"keyword="
            f"{keyword_score:.4f} "
            f"edge="
            f"{edge_score:.4f} "
            f"centrality="
            f"{centrality_score:.4f}"
        )

    # -----------------------------------------------------
    # Ranking
    # -----------------------------------------------------

    add_rank(
        results,
        "semantic_keyword_jaccard",
        "keyword_rank"
    )

    add_rank(
        results,
        "soft_weighted_edge_jaccard",
        "edge_rank"
    )

    add_rank(
        results,
        "weighted_centrality_cosine",
        "centrality_rank"
    )

    print_ranking(
        results,
        "semantic_keyword_jaccard",
        "Semantic Keyword Jaccard Ranking"
    )

    print_ranking(
        results,
        "soft_weighted_edge_jaccard",
        "Soft Semantic Edge Ranking"
    )

    print_ranking(
        results,
        "weighted_centrality_cosine",
        "Weighted Centrality Ranking"
    )

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    output = {

        "target": {

            "company_name":
                target_company.get(
                    "company_name"
                ),

            "corp_code":
                target_company.get(
                    "corp_code"
                ),

            "stock_code":
                target_company.get(
                    "stock_code"
                ),

            "core_evidence_count":
                len(target_sentences),

            "keywords":
                target_keyword_data,

            "graph":
                graph_summary(
                    target_graph
                ),
        },

        "config": {

            "keyword_model":
                KEYWORD_MODEL_NAME,

            "keywords_per_sentence":
                KEYWORDS_PER_SENTENCE,

            "max_keywords_per_company":
                MAX_KEYWORDS_PER_COMPANY,

            "min_keybert_score":
                MIN_KEYBERT_SCORE,

            "ngram_range":
                list(NGRAM_RANGE),

            "mmr_diversity":
                MMR_DIVERSITY,

            "node_match_threshold":
                NODE_MATCH_THRESHOLD,

            "edge_match_threshold":
                EDGE_MATCH_THRESHOLD,

            "node_alignment":
                (
                    "dynamic semantic "
                    "one-to-one alignment"
                ),

            "edge_alignment":
                (
                    "soft semantic "
                    "one-to-one edge alignment"
                ),

            "edge_weight":
                (
                    "same-core-sentence "
                    "co-occurrence frequency"
                ),

            "fusion_weight":
                None,
        },

        "candidate_count":
            len(results),

        "results":
            results,
    }

    save_json(
        OUTPUT_PATH,
        output
    )

    print()
    print("=" * 100)

    print(
        f"저장 완료: "
        f"{OUTPUT_PATH}"
    )

    print("=" * 100)


if __name__ == "__main__":
    main()