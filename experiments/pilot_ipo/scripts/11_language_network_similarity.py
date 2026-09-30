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

PROJECT_ROOT = Path(
    "experiments/pilot_ipo"
)

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

# 한 기업에서 최종적으로 사용할 최대 node 수
MAX_KEYWORDS_PER_COMPANY = 60

# 너무 낮은 KeyBERT 후보 제거
MIN_KEYBERT_SCORE = 0.35


# ---------------------------------------------------------
# Semantic Node Alignment Threshold
#
# APR keyword와 candidate keyword의 cosine similarity가
# 이 값 이상이면 "의미적으로 비슷한 node 후보"로 인정.
#
# 가중치가 아니라 실험용 threshold.
# ---------------------------------------------------------

NODE_MATCH_THRESHOLD = 0.75


# ---------------------------------------------------------
# Semantic Edge Alignment Threshold
#
# 두 edge의 양 끝 node가 의미적으로 유사한 경우
# 비슷한 관계로 인정.
#
# 가중치가 아니라 threshold.
# ---------------------------------------------------------

EDGE_MATCH_THRESHOLD = 0.70


# =========================================================
# 3. 일반 Keyword Noise
#
# 여기 있는 것은 KeyBERT 추출 단계에서 제거.
#
# 도메인 vocabulary를 미리 정하는 것이 아니라
# 일반적인 문장 표현 / boilerplate만 최소 제거.
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
# 4. Centrality 전용 Noise
#
# 중요:
#
# 이 표현들은 Keyword / Edge 단계에서는 제거하지 않는다.
#
# 이유:
# 새로운 concept 발견 가능성은 유지하면서,
# Centrality에서 공시 형식/법률 표현이
# "사업의 중심 node"가 되는 것만 막기 위함.
# =========================================================

CENTRALITY_NOISE_PHRASES = {
    # -----------------------------------------------------
    # 공시 문서 구조
    # -----------------------------------------------------
    "주요 연혁",
    "연혁",
    "주1",
    "주 1",
    "사업내용은 다음",
    "사업영역을 요약",
    "사업내용을 요약",

    # -----------------------------------------------------
    # 법률 / 규정
    # -----------------------------------------------------
    "독점규제",
    "공정거래",
    "독점규제및공정거래에관한법률",
    "화장품법",
    "관련 법률",
    "법률",

    # -----------------------------------------------------
    # 지배구조 / 형식정보
    # -----------------------------------------------------
    "대표이사",
    "주요 임원",
    "임원들은",
    "임원은",
    "피합병법인",
    "합병법인",
    "지분 보유",

    # -----------------------------------------------------
    # 문서형 일반 표현
    # -----------------------------------------------------
    "선정",
    "향후 필요한",
    "reason 가치",
}


# =========================================================
# 5. JSON
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
# 6. Target Profile 찾기
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

        data = load_json(
            path
        )

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
# 7. Core Evidence 추출
# =========================================================

def extract_core_sentences(
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

    sentences = []

    for item in core_evidence:

        text = (
            item.get(
                "text",
                ""
            ).strip()
        )

        if text:
            sentences.append(
                text
            )

    return sentences


# =========================================================
# 8. Keyword Normalize
#
# 공격적으로 한국어 조사를 잘라내지 않는다.
#
# 이전 방식에서는:
#
# 증가하는 -> 증가하
# 판매하는 -> 판매하
#
# 같은 이상한 형태가 생길 수 있었기 때문.
# =========================================================

def normalize_keyword(
    keyword
):

    keyword = (
        keyword
        .lower()
        .strip()
    )

    # 특수문자 제거
    keyword = re.sub(
        r"[^\w가-힣a-zA-Z\s\-]",
        " ",
        keyword
    )

    # 중복 공백 제거
    keyword = re.sub(
        r"\s+",
        " ",
        keyword
    ).strip()

    if not keyword:
        return ""

    tokens = []

    for token in keyword.split():

        if token in GENERIC_STOPWORDS:
            continue

        # 숫자로만 이루어진 token
        if re.fullmatch(
            r"\d+(\.\d+)?",
            token
        ):
            continue

        tokens.append(
            token
        )

    keyword = " ".join(
        tokens
    ).strip()

    if len(keyword) < 2:
        return ""

    return keyword


# =========================================================
# 9. 일반 Keyword Noise Filter
# =========================================================

def is_noisy_keyword(
    keyword,
    score
):

    if not keyword:
        return True

    # KeyBERT relevance가 너무 낮음
    if score < MIN_KEYBERT_SCORE:
        return True

    lowered = (
        keyword
        .lower()
        .strip()
    )

    for phrase in GENERIC_NOISE_PHRASES:

        if phrase in lowered:
            return True

    # 숫자 중심 표현
    if re.fullmatch(
        r"[\d\s.%]+",
        lowered
    ):
        return True

    # 날짜/연도 위주의 짧은 표현
    if (
        re.search(
            r"\d{4}년|\d+월|\d+일",
            lowered
        )
        and len(
            lowered.split()
        ) <= 2
    ):
        return True

    if len(
        lowered.replace(
            " ",
            ""
        )
    ) < 2:
        return True

    return False


# =========================================================
# 10. Sentence-level KeyBERT
#
# 문서 전체를 한 번에 keyword화하지 않고,
# 각 core_evidence 문장마다 keyword를 추출한다.
#
# 이유:
# 같은 core sentence 안에 등장한 keyword들을
# Edge로 연결하기 위해서.
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
            keyphrase_ngram_range=
                NGRAM_RANGE,
            stop_words=None,
            top_n=
                KEYWORDS_PER_SENTENCE,
            use_mmr=True,
            diversity=
                MMR_DIVERSITY
        )
    )

    sentence_keywords = []

    for (
        sentence,
        keyword_list
    ) in zip(
        sentences,
        raw_results
    ):

        cleaned = []
        seen = set()

        for (
            keyword,
            score
        ) in keyword_list:

            score = float(
                score
            )

            normalized = (
                normalize_keyword(
                    keyword
                )
            )

            if is_noisy_keyword(
                normalized,
                score
            ):
                continue

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            cleaned.append(
                {
                    "keyword":
                        normalized,

                    "score":
                        score,
                }
            )

        sentence_keywords.append(
            {
                "sentence":
                    sentence,

                "keywords":
                    cleaned,
            }
        )

    return sentence_keywords


# =========================================================
# 11. 기업 Keyword 집계
#
# frequency:
# 해당 keyword가 몇 개 core 문장에서 발견됐는가
#
# mean_keybert_score:
# 해당 keyword의 평균 KeyBERT relevance
#
# importance:
# frequency * mean_keybert_score
#
# 사람이 설정한 가중치가 아니라 데이터 기반 값.
# =========================================================

def aggregate_keywords(
    sentence_keywords
):

    accumulator = {}

    for item in sentence_keywords:

        for keyword_item in item[
            "keywords"
        ]:

            keyword = (
                keyword_item[
                    "keyword"
                ]
            )

            score = (
                keyword_item[
                    "score"
                ]
            )

            if keyword not in accumulator:

                accumulator[
                    keyword
                ] = {
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

    for (
        keyword,
        data
    ) in accumulator.items():

        frequency = (
            data[
                "frequency"
            ]
        )

        mean_score = float(
            np.mean(
                data[
                    "scores"
                ]
            )
        )

        importance = float(
            frequency
            * mean_score
        )

        results.append(
            {
                "keyword":
                    keyword,

                "frequency":
                    frequency,

                "mean_keybert_score":
                    mean_score,

                "importance":
                    importance,
            }
        )

    results.sort(
        key=lambda item: (
            item[
                "importance"
            ],
            item[
                "frequency"
            ],
            item[
                "mean_keybert_score"
            ],
        ),
        reverse=True
    )

    return results[
        :MAX_KEYWORDS_PER_COMPANY
    ]


# =========================================================
# 12. Keyword Graph 생성
#
# Node:
# KeyBERT로 자유롭게 추출한 keyword
#
# Edge:
# 같은 core sentence에서 같이 나온 keyword pair
#
# Edge Weight:
# 해당 keyword pair가 몇 개 문장에서 동시출현했는가
# =========================================================

def build_keyword_graph(
    sentence_keywords,
    selected_keywords
):

    graph = nx.Graph()

    selected_map = {
        item["keyword"]:
            item
        for item
        in selected_keywords
    }

    selected_set = set(
        selected_map.keys()
    )

    # -----------------------------------------------------
    # Node
    # -----------------------------------------------------

    for (
        keyword,
        data
    ) in selected_map.items():

        graph.add_node(
            keyword,

            frequency=
                data[
                    "frequency"
                ],

            importance=
                data[
                    "importance"
                ],

            keybert_score=
                data[
                    "mean_keybert_score"
                ]
        )

    # -----------------------------------------------------
    # Edge
    # -----------------------------------------------------

    for sentence_item in sentence_keywords:

        found_keywords = []

        for keyword_item in sentence_item[
            "keywords"
        ]:

            keyword = (
                keyword_item[
                    "keyword"
                ]
            )

            if keyword in selected_set:

                found_keywords.append(
                    keyword
                )

        found_keywords = sorted(
            set(
                found_keywords
            )
        )

        for (
            keyword_a,
            keyword_b
        ) in combinations(
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
# 13. Centrality Noise 판단
#
# Keyword / Edge에는 적용하지 않는다.
#
# Centrality에서 사업 중심축으로 보기 어려운
# 공시 형식 / 법률 / 구조 표현만 제거한다.
# =========================================================

def is_centrality_noise_keyword(
    keyword
):

    if not keyword:
        return True

    normalized = (
        keyword
        .lower()
        .strip()
    )

    for phrase in CENTRALITY_NOISE_PHRASES:

        if (
            phrase.lower()
            in normalized
        ):
            return True

    # 주1 / 주 2 / 주3 ...
    if re.fullmatch(
        r"주\s*\d+",
        normalized
    ):
        return True

    # 숫자 중심 표현
    if re.fullmatch(
        r"[\d\s.,%()\-]+",
        normalized
    ):
        return True

    return False


# =========================================================
# 14. Centrality 전용 Business Graph
#
# 원본 그래프는 그대로 유지.
#
# 복사본에서 Centrality Noise만 제거한다.
#
# 따라서:
#
# Keyword 비교   -> 원본 graph
# Edge 비교      -> 원본 graph
# Centrality 비교 -> 정제 graph
# =========================================================

def build_centrality_graph(
    graph
):

    centrality_graph = (
        graph.copy()
    )

    remove_nodes = []

    for node in (
        centrality_graph.nodes()
    ):

        if is_centrality_noise_keyword(
            node
        ):

            remove_nodes.append(
                node
            )

    centrality_graph.remove_nodes_from(
        remove_nodes
    )

    # 연결이 하나도 없는 node 제거
    isolates = list(
        nx.isolates(
            centrality_graph
        )
    )

    centrality_graph.remove_nodes_from(
        isolates
    )

    return centrality_graph


# =========================================================
# 15. Keyword Embedding
#
# BGE 기업 임베딩과 목적이 다르다.
#
# 여기서는 오직:
#
# APR keyword와 candidate keyword가
# 의미적으로 같은 concept인지 정렬하는
# 보조 도구로만 사용.
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

    vectors = (
        sentence_model.encode(
            keywords,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )
    )

    return np.asarray(
        vectors,
        dtype=np.float32
    )


# =========================================================
# 16. Node Similarity Matrix
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
                len(
                    target_vectors
                ),
                len(
                    candidate_vectors
                )
            ),
            dtype=np.float32
        )

    return (
        target_vectors
        @ candidate_vectors.T
    )


# =========================================================
# 17. Semantic Node Alignment
#
# 공통 vocabulary를 미리 정하지 않는다.
#
# APR와 candidate가 각자 자유롭게 keyword를 추출한 뒤
# embedding cosine similarity를 이용해
# 의미적으로 가까운 node를 one-to-one 매칭.
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
        key=lambda item:
            item[0],
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

        used_target.add(
            target_index
        )

        used_candidate.add(
            candidate_index
        )

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

    return (
        matches,
        mapping
    )


# =========================================================
# 18. Semantic Keyword Jaccard
#
# exact string이 아니라
# semantic node matching 개수를 교집합처럼 사용.
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

    matched_count = (
        len(
            matches
        )
    )

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
# 19. Candidate Graph Node Alignment
#
# Centrality 비교를 위해
#
# 후보의 semantic-matched node를
# APR node 이름으로 정렬한다.
#
# 매칭되지 않은 후보 node는
# __candidate__ prefix를 붙여 별도로 유지.
# =========================================================

def align_candidate_graph(
    candidate_graph,
    mapping
):

    aligned_graph = nx.Graph()

    for (
        node,
        data
    ) in candidate_graph.nodes(
        data=True
    ):

        if node in mapping:

            aligned_node = (
                mapping[
                    node
                ]
            )

        else:

            aligned_node = (
                f"__candidate__::{node}"
            )

        if (
            aligned_node
            not in aligned_graph
        ):

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

        aligned_a = (
            mapping.get(
                node_a,
                f"__candidate__::{node_a}"
            )
        )

        aligned_b = (
            mapping.get(
                node_b,
                f"__candidate__::{node_b}"
            )
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
# 20. Semantic Edge Similarity
#
# APR:
# A -- B
#
# Candidate:
# C -- D
#
# direct:
# A↔C / B↔D
#
# reverse:
# A↔D / B↔C
#
# 두 방향 중 더 좋은 것을 사용.
#
# 각 방향에서는 min()을 사용해서
# edge 한쪽만 비슷한 경우 과대평가를 막는다.
# =========================================================

def edge_semantic_similarity(
    target_edge,
    candidate_edge,
    target_index_map,
    candidate_index_map,
    similarity_matrix
):

    (
        target_a,
        target_b
    ) = target_edge

    (
        candidate_a,
        candidate_b
    ) = candidate_edge

    ta = target_index_map[
        target_a
    ]

    tb = target_index_map[
        target_b
    ]

    ca = candidate_index_map[
        candidate_a
    ]

    cb = candidate_index_map[
        candidate_b
    ]

    # -----------------------------------------------------
    # 같은 방향
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 반대 방향
    # -----------------------------------------------------

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
# 21. Soft Weighted Edge Jaccard
#
# exact edge 문자열 일치가 아니라
# semantic edge matching을 사용.
#
# Edge weight는:
# 같은 core sentence에서 동시출현한 횟수.
#
# 사람이 정한 임의 가중치가 아님.
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

        return (
            0.0,
            []
        )

    target_index_map = {
        keyword: index
        for (
            index,
            keyword
        ) in enumerate(
            target_keywords
        )
    }

    candidate_index_map = {
        keyword: index
        for (
            index,
            keyword
        ) in enumerate(
            candidate_keywords
        )
    }

    target_edges = []

    for (
        node_a,
        node_b,
        data
    ) in target_graph.edges(
        data=True
    ):

        target_edges.append(
            {
                "nodes": (
                    node_a,
                    node_b
                ),

                "weight":
                    float(
                        data.get(
                            "weight",
                            1.0
                        )
                    ),
            }
        )

    candidate_edges = []

    for (
        node_a,
        node_b,
        data
    ) in candidate_graph.edges(
        data=True
    ):

        candidate_edges.append(
            {
                "nodes": (
                    node_a,
                    node_b
                ),

                "weight":
                    float(
                        data.get(
                            "weight",
                            1.0
                        )
                    ),
            }
        )

    match_candidates = []

    for (
        target_edge_index,
        target_edge
    ) in enumerate(
        target_edges
    ):

        for (
            candidate_edge_index,
            candidate_edge
        ) in enumerate(
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

                match_candidates.append(
                    (
                        similarity,
                        target_edge_index,
                        candidate_edge_index
                    )
                )

    match_candidates.sort(
        key=lambda item:
            item[0],
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
    ) in match_candidates:

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
            target_edge[
                "weight"
            ],
            candidate_edge[
                "weight"
            ]
        )

        contribution = (
            common_weight
            * similarity
        )

        matched_mass += (
            contribution
        )

        edge_matches.append(
            {
                "target_edge":
                    list(
                        target_edge[
                            "nodes"
                        ]
                    ),

                "candidate_edge":
                    list(
                        candidate_edge[
                            "nodes"
                        ]
                    ),

                "semantic_similarity":
                    float(
                        similarity
                    ),

                "target_weight":
                    target_edge[
                        "weight"
                    ],

                "candidate_weight":
                    candidate_edge[
                        "weight"
                    ],

                "matched_mass":
                    float(
                        contribution
                    ),
            }
        )

    target_total_weight = sum(
        edge[
            "weight"
        ]
        for edge
        in target_edges
    )

    candidate_total_weight = sum(
        edge[
            "weight"
        ]
        for edge
        in candidate_edges
    )

    denominator = (
        target_total_weight
        + candidate_total_weight
        - matched_mass
    )

    if denominator <= 0:

        return (
            0.0,
            edge_matches
        )

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
# 22. Weighted Degree Centrality
#
# 단순 edge 개수가 아니라
# edge weight = 동시출현 횟수까지 반영한다.
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
            for node
            in graph.nodes()
        }

    centrality = {}

    for node in graph.nodes():

        weighted_degree = float(
            graph.degree(
                node,
                weight="weight"
            )
        )

        centrality[
            node
        ] = (
            weighted_degree
            / (
                node_count
                - 1
            )
        )

    return centrality


# =========================================================
# 23. Weighted Centrality Cosine
#
# APR와 후보의 node를 의미적으로 align한 뒤,
# 각 node의 weighted degree 구조를 vector화하여
# cosine similarity 계산.
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
            for node
            in all_nodes
        ],
        dtype=np.float32
    )

    vector_b = np.array(
        [
            centrality_b.get(
                node,
                0.0
            )
            for node
            in all_nodes
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
# 24. Graph Summary
# =========================================================

def graph_summary(
    graph
):

    node_count = (
        graph.number_of_nodes()
    )

    edge_count = (
        graph.number_of_edges()
    )

    if node_count > 1:

        density = float(
            nx.density(
                graph
            )
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
            for node
            in graph.nodes()
        ],
        key=lambda item:
            item[1],
        reverse=True
    )

    top_central_keywords = [
        {
            "keyword":
                node,

            "weighted_degree":
                degree,
        }
        for (
            node,
            degree
        ) in weighted_degree[
            :10
        ]
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
# 25. Ranking
# =========================================================

def add_rank(
    results,
    metric_name,
    rank_name
):

    ranked = sorted(
        results,
        key=lambda item:
            item[
                metric_name
            ],
        reverse=True
    )

    for (
        rank,
        item
    ) in enumerate(
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
            item[
                metric_name
            ],
        reverse=True
    )

    print()
    print(
        "=" * 100
    )

    print(
        title
    )

    print(
        "=" * 100
    )

    for (
        rank,
        item
    ) in enumerate(
        ranked[
            :top_n
        ],
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
# 26. Company Network 생성
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
# 27. Main
# =========================================================

def main():

    print()
    print(
        "=" * 100
    )

    print(
        "PeerProof - Language Network Similarity v4"
    )

    print(
        "=" * 100
    )

    print()


    # =====================================================
    # Model Load
    # =====================================================

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

    print(
        "모델 로딩 완료"
    )

    print()


    # =====================================================
    # Target
    # =====================================================

    target_path = (
        find_target_profile()
    )

    target_profile = (
        load_json(
            target_path
        )
    )

    target_company = (
        target_profile[
            "company"
        ]
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
        item[
            "keyword"
        ]
        for item
        in target_keyword_data
    ]


    target_vectors = (
        embed_keywords(
            sentence_model,
            target_keywords
        )
    )


    # =====================================================
    # NEW v4
    #
    # Centrality 계산용 Target Graph 정제
    # =====================================================

    target_centrality_graph = (
        build_centrality_graph(
            target_graph
        )
    )


    print(
        f"Target Company          : "
        f"{target_company['company_name']}"
    )

    print(
        f"Target Core             : "
        f"{len(target_sentences)}"
    )

    print(
        f"Target Nodes            : "
        f"{target_graph.number_of_nodes()}"
    )

    print(
        f"Target Edges            : "
        f"{target_graph.number_of_edges()}"
    )

    print(
        f"Centrality Nodes        : "
        f"{target_centrality_graph.number_of_nodes()}"
    )

    print(
        f"Centrality Edges        : "
        f"{target_centrality_graph.number_of_edges()}"
    )

    print()


    print(
        "APR Top Keywords"
    )

    print(
        "-" * 100
    )

    for (
        index,
        item
    ) in enumerate(
        target_keyword_data[
            :20
        ],
        start=1
    ):

        print(
            f"{index:>2}. "
            f"{item['keyword']:<35} "
            f"freq="
            f"{item['frequency']:>2} "
            f"score="
            f"{item['mean_keybert_score']:.4f}"
        )


    print()
    print(
        "APR Centrality Graph - "
        "Top Business Nodes"
    )

    print(
        "-" * 100
    )

    target_centrality_summary = (
        graph_summary(
            target_centrality_graph
        )
    )

    for (
        index,
        item
    ) in enumerate(
        target_centrality_summary[
            "top_central_keywords"
        ],
        start=1
    ):

        print(
            f"{index:>2}. "
            f"{item['keyword']:<35} "
            f"weighted_degree="
            f"{item['weighted_degree']:.2f}"
        )


    # =====================================================
    # Candidates
    # =====================================================

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

    total = len(
        candidates
    )


    print()
    print(
        "=" * 100
    )

    print(
        "Candidate Language Networks"
    )

    print(
        "=" * 100
    )


    for (
        index,
        candidate
    ) in enumerate(
        candidates,
        start=1
    ):

        company = (
            candidate.get(
                "company",
                {}
            )
        )

        company_name = (
            company.get(
                "company_name"
            )
        )

        stock_code = (
            company.get(
                "stock_code"
            )
        )

        corp_code = (
            company.get(
                "corp_code"
            )
        )


        sentences = (
            extract_core_sentences(
                candidate
            )
        )

        if not sentences:
            continue


        # -------------------------------------------------
        # Candidate Network
        # -------------------------------------------------

        (
            candidate_sentence_keywords,
            candidate_keyword_data,
            candidate_graph
        ) = build_company_network(
            keyword_model,
            sentences
        )


        candidate_keywords = [
            item[
                "keyword"
            ]
            for item
            in candidate_keyword_data
        ]


        candidate_vectors = (
            embed_keywords(
                sentence_model,
                candidate_keywords
            )
        )


        # -------------------------------------------------
        # Node Similarity Matrix
        # -------------------------------------------------

        similarity_matrix = (
            build_node_similarity_matrix(
                target_vectors,
                candidate_vectors
            )
        )


        # -------------------------------------------------
        # Semantic Node Alignment
        # -------------------------------------------------

        (
            node_matches,
            node_mapping
        ) = align_nodes(
            target_keywords,
            candidate_keywords,
            similarity_matrix
        )


        # -------------------------------------------------
        # Candidate Graph를 APR node 공간으로 정렬
        # -------------------------------------------------

        aligned_candidate_graph = (
            align_candidate_graph(
                candidate_graph,
                node_mapping
            )
        )


        # -------------------------------------------------
        # 1. Semantic Keyword Jaccard
        # -------------------------------------------------

        keyword_score = (
            semantic_keyword_jaccard(
                target_graph,
                candidate_graph,
                node_matches
            )
        )


        # -------------------------------------------------
        # 2. Soft Semantic Edge
        # -------------------------------------------------

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


        # -------------------------------------------------
        # 3. Centrality
        #
        # v4:
        # Centrality 계산에서만 노이즈 node 제거
        # -------------------------------------------------

        candidate_centrality_graph = (
            build_centrality_graph(
                aligned_candidate_graph
            )
        )


        centrality_score = (
            weighted_centrality_cosine(
                target_centrality_graph,
                candidate_centrality_graph
            )
        )


        # -------------------------------------------------
        # Result
        # -------------------------------------------------

        result = {

            "company_name":
                company_name,

            "stock_code":
                stock_code,

            "corp_code":
                corp_code,

            "core_evidence_count":
                len(
                    sentences
                ),

            "keyword_count":
                len(
                    candidate_keywords
                ),

            # ---------------------------------------------
            # Node
            # ---------------------------------------------

            "semantic_node_match_count":
                len(
                    node_matches
                ),

            "semantic_node_matches":
                node_matches[
                    :20
                ],

            # ---------------------------------------------
            # Edge
            # ---------------------------------------------

            "semantic_edge_match_count":
                len(
                    edge_matches
                ),

            "semantic_edge_matches":
                edge_matches[
                    :20
                ],

            # ---------------------------------------------
            # Keyword
            # ---------------------------------------------

            "keywords":
                candidate_keyword_data,

            # ---------------------------------------------
            # Original Graph
            # ---------------------------------------------

            "graph":
                graph_summary(
                    candidate_graph
                ),

            # ---------------------------------------------
            # NEW v4:
            # Centrality 전용 정제 Graph
            # ---------------------------------------------

            "centrality_graph":
                graph_summary(
                    candidate_centrality_graph
                ),

            # ---------------------------------------------
            # Similarity
            # ---------------------------------------------

            "semantic_keyword_jaccard":
                float(
                    keyword_score
                ),

            "soft_weighted_edge_jaccard":
                float(
                    edge_score
                ),

            "weighted_centrality_cosine":
                float(
                    centrality_score
                ),
        }


        results.append(
            result
        )


        print(
            f"[{index}/{total}] "
            f"{company_name:<20} | "
            f"nodes="
            f"{candidate_graph.number_of_nodes():>2} "
            f"edges="
            f"{candidate_graph.number_of_edges():>3} "
            f"central_nodes="
            f"{candidate_centrality_graph.number_of_nodes():>2} "
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


    # =====================================================
    # Ranking
    # =====================================================

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
        "Filtered Weighted Centrality Ranking"
    )


    # =====================================================
    # Save
    # =====================================================

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
                len(
                    target_sentences
                ),

            "keywords":
                target_keyword_data,

            # 원본
            "graph":
                graph_summary(
                    target_graph
                ),

            # Centrality 전용 정제본
            "centrality_graph":
                graph_summary(
                    target_centrality_graph
                ),
        },


        "config": {

            "version":
                "v4",

            "keyword_model":
                KEYWORD_MODEL_NAME,

            "keywords_per_sentence":
                KEYWORDS_PER_SENTENCE,

            "max_keywords_per_company":
                MAX_KEYWORDS_PER_COMPANY,

            "min_keybert_score":
                MIN_KEYBERT_SCORE,

            "ngram_range":
                list(
                    NGRAM_RANGE
                ),

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

            "centrality_method":
                (
                    "weighted degree centrality "
                    "cosine after semantic node alignment"
                ),

            "centrality_graph":
                (
                    "original semantic network "
                    "minus disclosure/legal/"
                    "structural noise nodes"
                ),

            "centrality_noise_filter":
                sorted(
                    CENTRALITY_NOISE_PHRASES
                ),

            # 아직 지표 간 fusion 가중치는 없음
            "fusion_weight":
                None,
        },


        "candidate_count":
            len(
                results
            ),

        "results":
            results,
    }


    save_json(
        OUTPUT_PATH,
        output
    )


    print()
    print(
        "=" * 100
    )

    print(
        f"저장 완료: "
        f"{OUTPUT_PATH}"
    )

    print(
        "=" * 100
    )


if __name__ == "__main__":
    main()