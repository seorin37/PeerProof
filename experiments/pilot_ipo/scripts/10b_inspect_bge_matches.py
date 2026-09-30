import json
from pathlib import Path

import numpy as np
from FlagEmbedding import BGEM3FlagModel


# =========================================================
# 1. 경로
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


# =========================================================
# 2. 모델 설정
# =========================================================

MODEL_NAME = "BAAI/bge-m3"

BATCH_SIZE = 16

MAX_LENGTH = 8192


# =========================================================
# 3. 검증 대상
# =========================================================

INSPECT_COMPANIES = [
    "아우딘퓨쳐스",
    "제이시스메디칼",
    "뷰티스킨",
    "네오팜",
    "한국콜마",
    "클래시스",
]

TOP_K = 5


# =========================================================
# 4. JSON
# =========================================================

def load_json(path):

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# =========================================================
# 5. Target Profile 찾기
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
            data.get(
                "company",
                {}
            ).get(
                "company_name"
            )
        )

        if company_name == "에이피알":

            return path

    raise RuntimeError(
        "에이피알 business_profile.json을 찾지 못했습니다."
    )


# =========================================================
# 6. Core Evidence 추출
# =========================================================

def extract_core_evidence(profile):

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
                "text": text,

                "categories":
                    item.get(
                        "categories",
                        []
                    ),

                "relevance_score":
                    item.get(
                        "relevance_score"
                    ),
            }
        )

    return results


# =========================================================
# 7. 임베딩
# =========================================================

def embed_texts(
    model,
    texts
):

    output = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        max_length=MAX_LENGTH,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False
    )

    vectors = np.asarray(
        output["dense_vecs"],
        dtype=np.float32
    )

    # 각 문장 벡터 L2 normalize
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
# 8. 모든 문장쌍 cosine 계산
# =========================================================

def calculate_sentence_matches(
    target_evidence,
    candidate_evidence,
    target_vectors,
    candidate_vectors
):

    # normalize 되어 있으므로
    # dot product = cosine similarity
    similarity_matrix = (
        target_vectors
        @ candidate_vectors.T
    )

    matches = []

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

            matches.append(
                {
                    "similarity":
                        similarity,

                    "target_index":
                        target_index,

                    "candidate_index":
                        candidate_index,

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

    matches.sort(
        key=lambda x:
            x["similarity"],
        reverse=True
    )

    return matches


# =========================================================
# 9. 중복 문장 과다 출력 방지
#
# 같은 APR 문장 하나가 후보 문장 여러 개와
# 계속 Top에 나오는 것을 조금 완화하기 위함
# =========================================================

def select_diverse_top_matches(
    matches,
    top_k
):

    selected = []

    used_target = set()
    used_candidate = set()

    # 1차:
    # target / candidate 문장이 모두
    # 아직 안 쓰인 경우 우선 선택
    for match in matches:

        ti = match[
            "target_index"
        ]

        ci = match[
            "candidate_index"
        ]

        if (
            ti not in used_target
            and
            ci not in used_candidate
        ):

            selected.append(
                match
            )

            used_target.add(
                ti
            )

            used_candidate.add(
                ci
            )

        if len(
            selected
        ) >= top_k:

            return selected

    # 2차:
    # 부족하면 similarity 순으로 채움
    for match in matches:

        if match in selected:

            continue

        selected.append(
            match
        )

        if len(
            selected
        ) >= top_k:

            break

    return selected


# =========================================================
# 10. 출력
# =========================================================

def print_match(
    rank,
    match
):

    print(
        "-" * 100
    )

    print(
        f"[문장쌍 {rank}] "
        f"similarity="
        f"{match['similarity']:.4f}"
    )

    print()

    print(
        "[APR]"
    )

    print(
        f"categories="
        f"{match['target']['categories']}"
    )

    print(
        match[
            "target"
        ][
            "text"
        ]
    )

    print()

    print(
        "[Candidate]"
    )

    print(
        f"categories="
        f"{match['candidate']['categories']}"
    )

    print(
        match[
            "candidate"
        ][
            "text"
        ]
    )

    print()


# =========================================================
# 11. Main
# =========================================================

def main():

    print()

    print(
        "=" * 100
    )

    print(
        "PeerProof - BGE Sentence Match Inspection"
    )

    print(
        "=" * 100
    )

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

    target_evidence = (
        extract_core_evidence(
            target_profile
        )
    )

    target_texts = [
        item["text"]
        for item in target_evidence
    ]


    print(
        f"Target         : 에이피알"
    )

    print(
        f"Target Core    : "
        f"{len(target_evidence)}"
    )

    print()


    # -----------------------------------------------------
    # Candidate
    # -----------------------------------------------------

    candidate_data = (
        load_json(
            CANDIDATE_PROFILES_PATH
        )
    )

    profiles = (
        candidate_data.get(
            "profiles",
            []
        )
    )

    candidate_map = {}

    for profile in profiles:

        company_name = (
            profile.get(
                "company",
                {}
            ).get(
                "company_name"
            )
        )

        if company_name:

            candidate_map[
                company_name
            ] = profile


    # -----------------------------------------------------
    # Model
    # -----------------------------------------------------

    print(
        "BGE-M3 모델 로딩..."
    )

    model = BGEM3FlagModel(
        MODEL_NAME,
        use_fp16=True
    )

    print(
        "BGE-M3 모델 로딩 완료"
    )

    print()


    # -----------------------------------------------------
    # Target embedding은 1번만
    # -----------------------------------------------------

    print(
        "APR core_evidence embedding 생성..."
    )

    target_vectors = (
        embed_texts(
            model,
            target_texts
        )
    )

    print(
        f"APR embeddings shape: "
        f"{target_vectors.shape}"
    )

    print()


    # -----------------------------------------------------
    # 기업별 검사
    # -----------------------------------------------------

    for company_name in INSPECT_COMPANIES:

        if company_name not in candidate_map:

            print(
                f"[WARN] 후보 profile 없음: "
                f"{company_name}"
            )

            continue


        profile = (
            candidate_map[
                company_name
            ]
        )

        candidate_evidence = (
            extract_core_evidence(
                profile
            )
        )

        candidate_texts = [
            item["text"]
            for item in candidate_evidence
        ]


        print()

        print(
            "=" * 100
        )

        print(
            f"{company_name}"
        )

        print(
            f"Candidate Core : "
            f"{len(candidate_evidence)}"
        )

        print(
            "=" * 100
        )

        print()


        candidate_vectors = (
            embed_texts(
                model,
                candidate_texts
            )
        )


        matches = (
            calculate_sentence_matches(
                target_evidence=
                    target_evidence,

                candidate_evidence=
                    candidate_evidence,

                target_vectors=
                    target_vectors,

                candidate_vectors=
                    candidate_vectors
            )
        )


        top_matches = (
            select_diverse_top_matches(
                matches,
                TOP_K
            )
        )


        for rank, match in enumerate(
            top_matches,
            start=1
        ):

            print_match(
                rank,
                match
            )


if __name__ == "__main__":
    main()
