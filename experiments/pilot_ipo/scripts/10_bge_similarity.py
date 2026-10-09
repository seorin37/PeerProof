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

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "bge_similarity.json"
)


# =========================================================
# 2. 모델 설정
# =========================================================

MODEL_NAME = "BAAI/bge-m3"

MAX_LENGTH = 8192

BATCH_SIZE = 16


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
# 4. Target Business Profile 찾기
# =========================================================

def apply_cli_overrides():
    """기본 경로는 그대로 두고, 인자로 준 경우에만 입력/출력 경로를 바꾼다."""
    import argparse

    global CANDIDATE_PROFILES_PATH, OUTPUT_PATH, TARGET_PROFILE_OVERRIDE

    parser = argparse.ArgumentParser(description="유사도 계산")
    parser.add_argument("--target-profile", help="대상기업 프로필 JSON (기본: companies/*/business_profile.json)")
    parser.add_argument("--candidates", help="후보 프로필 JSON (기본: candidate_profiles/profiles.json)")
    parser.add_argument("--output", help="결과 JSON 경로 (기본: 이전 결과 파일을 덮어쓴다)")
    args = parser.parse_args()

    if args.target_profile:
        TARGET_PROFILE_OVERRIDE = Path(args.target_profile)
    if args.candidates:
        CANDIDATE_PROFILES_PATH = Path(args.candidates)
    if args.output:
        OUTPUT_PATH = Path(args.output)


TARGET_PROFILE_OVERRIDE = None


def find_target_profile():

    if TARGET_PROFILE_OVERRIDE is not None:

        return TARGET_PROFILE_OVERRIDE

    matches = list(
        TARGET_COMPANIES_DIR.glob(
            "*/business_profile.json"
        )
    )

    if not matches:

        raise FileNotFoundError(
            "Target business_profile.json이 없습니다."
        )

    # 현재 pilot에서는 APR 1개만 존재한다고 가정
    if len(matches) > 1:

        valid = []

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

                valid.append(
                    path
                )

        if len(valid) != 1:

            raise RuntimeError(
                "Target business_profile.json을 "
                "유일하게 찾을 수 없습니다."
            )

        return valid[0]

    return matches[0]


# =========================================================
# 5. Core Evidence 문장 추출
# =========================================================

def extract_core_sentences(
    profile_data
):

    business_profile = (
        profile_data.get(
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
            )
            .strip()
        )

        if text:

            sentences.append(
                text
            )

    return sentences


# =========================================================
# 6. 문장 임베딩
# =========================================================

def embed_sentences(
    model,
    sentences
):

    if not sentences:

        return None

    output = model.encode(
        sentences,
        batch_size=BATCH_SIZE,
        max_length=MAX_LENGTH,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False
    )

    embeddings = (
        output[
            "dense_vecs"
        ]
    )

    return np.asarray(
        embeddings,
        dtype=np.float32
    )


# =========================================================
# 7. 기업 대표 벡터
#
# 문장별 BGE embedding
# → 평균
# → L2 normalize
# =========================================================

def build_company_vector(
    model,
    sentences
):

    embeddings = (
        embed_sentences(
            model,
            sentences
        )
    )

    if embeddings is None:

        return None

    company_vector = (
        embeddings.mean(
            axis=0
        )
    )

    norm = np.linalg.norm(
        company_vector
    )

    if norm == 0:

        return None

    company_vector = (
        company_vector
        / norm
    )

    return company_vector


# =========================================================
# 8. Cosine Similarity
#
# 두 벡터가 L2 normalize 되어 있으므로
# dot product = cosine similarity
# =========================================================

def cosine_similarity(
    vector_a,
    vector_b
):

    return float(
        np.dot(
            vector_a,
            vector_b
        )
    )


# =========================================================
# 9. Main
# =========================================================

def main():

    apply_cli_overrides()

    print()

    print(
        "=" * 100
    )

    print(
        "PeerProof - BGE-M3 Similarity"
    )

    print(
        "=" * 100
    )

    print()


    # =====================================================
    # Target
    # =====================================================

    target_profile_path = (
        find_target_profile()
    )

    target_profile = (
        load_json(
            target_profile_path
        )
    )

    target_company = (
        target_profile[
            "company"
        ]
    )

    target_name = (
        target_company[
            "company_name"
        ]
    )

    target_sentences = (
        extract_core_sentences(
            target_profile
        )
    )


    print(
        f"Target Company : "
        f"{target_name}"
    )

    print(
        f"Target Core    : "
        f"{len(target_sentences)}"
    )

    print()


    # =====================================================
    # Candidate Profiles
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


    print(
        f"Candidates     : "
        f"{len(candidates)}"
    )

    print()


    # =====================================================
    # Model
    # =====================================================

    print(
        "BGE-M3 모델 로딩..."
    )

    model = (
        BGEM3FlagModel(
            MODEL_NAME,
            use_fp16=True
        )
    )

    print(
        "BGE-M3 모델 로딩 완료"
    )

    print()


    # =====================================================
    # Target vector
    # =====================================================

    print(
        "Target embedding 생성..."
    )

    target_vector = (
        build_company_vector(
            model,
            target_sentences
        )
    )

    if target_vector is None:

        raise RuntimeError(
            "Target vector 생성 실패"
        )


    print(
        f"Target Vector Shape : "
        f"{target_vector.shape}"
    )

    print()


    # =====================================================
    # Candidate similarity
    # =====================================================

    results = []

    total = len(
        candidates
    )


    for index, candidate in enumerate(
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

            print(
                f"[WARN] "
                f"{company_name} "
                f"core_evidence 없음"
            )

            continue


        candidate_vector = (
            build_company_vector(
                model,
                sentences
            )
        )


        if candidate_vector is None:

            print(
                f"[WARN] "
                f"{company_name} "
                f"vector 생성 실패"
            )

            continue


        similarity = (
            cosine_similarity(
                target_vector,
                candidate_vector
            )
        )


        result = {

            "company_name":
                company_name,

            "corp_code":
                corp_code,

            "stock_code":
                stock_code,

            "core_evidence_count":
                len(
                    sentences
                ),

            "bge_similarity":
                similarity,

            "prefilter_score":
                candidate.get(
                    "candidate_metadata",
                    {}
                ).get(
                    "prefilter_score"
                ),

            "market":
                candidate.get(
                    "candidate_metadata",
                    {}
                ).get(
                    "market"
                ),
        }

        results.append(
            result
        )


        print(
            f"[{index}/{total}] "
            f"{company_name:<20} "
            f"core={len(sentences):>2} "
            f"similarity={similarity:.4f}"
        )


    # =====================================================
    # Ranking
    # =====================================================

    results.sort(
        key=lambda x:
            x[
                "bge_similarity"
            ],
        reverse=True
    )


    for rank, result in enumerate(
        results,
        start=1
    ):

        result[
            "rank"
        ] = rank


    # =====================================================
    # 출력
    # =====================================================

    print()

    print(
        "=" * 100
    )

    print(
        "BGE-M3 Similarity Ranking"
    )

    print(
        "=" * 100
    )

    print()


    for result in results[:20]:

        print(
            f"#{result['rank']:>2} "
            f"{result['company_name']:<20} "
            f"{result['stock_code']} | "
            f"similarity="
            f"{result['bge_similarity']:.4f} | "
            f"core="
            f"{result['core_evidence_count']}"
        )


    # =====================================================
    # 저장
    # =====================================================

    output = {

        "target": {

            "company_name":
                target_name,

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
        },

        "model": {

            "name":
                MODEL_NAME,

            "embedding_method":
                "core_evidence sentence embeddings mean pooling",

            "similarity":
                "cosine",

            "max_length":
                MAX_LENGTH,
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
