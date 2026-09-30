import importlib.util
import json
from pathlib import Path


# =========================================================
# 1. 기본 경로
# =========================================================

PROJECT_ROOT = Path("experiments/pilot_ipo")

CANDIDATE_POOL_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "candidate_pool_stage2.json"
)

CACHE_DIR = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "candidate_business"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "candidate_profiles"
)

OUTPUT_ALL_PATH = (
    OUTPUT_DIR
    / "profiles.json"
)

SCRIPT_07_PATH = (
    PROJECT_ROOT
    / "scripts"
    / "07_build_business_profile.py"
)


# =========================================================
# 2. JSON
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
# 3. 07 모듈 불러오기
#
# 파일명이 숫자로 시작하므로 일반 import 대신
# importlib 사용
# =========================================================

def load_profile_module():

    if not SCRIPT_07_PATH.exists():

        raise FileNotFoundError(
            f"07 스크립트를 찾을 수 없습니다: "
            f"{SCRIPT_07_PATH}"
        )

    spec = (
        importlib.util.spec_from_file_location(
            "business_profile_builder",
            SCRIPT_07_PATH
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):

        raise RuntimeError(
            "07_build_business_profile.py "
            "모듈 로드 실패"
        )

    module = (
        importlib.util.module_from_spec(
            spec
        )
    )

    spec.loader.exec_module(
        module
    )

    return module


# =========================================================
# 4. Candidate company 객체 구성
# =========================================================

def build_company_object(
    candidate,
    analysis_as_of
):

    return {

        "company_name":
            candidate.get(
                "company_name"
            ),

        "corp_code":
            candidate.get(
                "corp_code"
            ),

        "stock_code":
            candidate.get(
                "stock_code"
            ),

        "analysis_as_of":
            analysis_as_of,
    }


# =========================================================
# 5. source filing 정보 구성
# =========================================================

def build_source(
    candidate
):

    filing = (
        candidate.get(
            "source_filing",
            {}
        )
        or {}
    )

    return {

        "rcept_no":
            filing.get(
                "rcept_no"
            ),

        "rcept_dt":
            filing.get(
                "rcept_dt"
            ),

        "report_nm":
            filing.get(
                "report_nm"
            ),
    }


# =========================================================
# 6. Main
# =========================================================

def main():

    print()

    print(
        "=" * 100
    )

    print(
        "PeerProof - Candidate Business Profile Builder"
    )

    print(
        "=" * 100
    )

    print()


    # =====================================================
    # 07 공통 모듈
    # =====================================================

    profile_module = (
        load_profile_module()
    )

    (
        category_keywords,
        domain_name
    ) = (
        profile_module.load_profile_keywords()
    )


    # =====================================================
    # 후보 50개
    # =====================================================

    candidate_pool = (
        load_json(
            CANDIDATE_POOL_PATH
        )
    )

    analysis_as_of = (
        candidate_pool.get(
            "analysis_as_of"
        )
    )

    candidates = (
        candidate_pool.get(
            "companies",
            []
        )
    )


    print(
        f"Analysis As Of : "
        f"{analysis_as_of}"
    )

    print(
        f"Domain         : "
        f"{domain_name}"
    )

    print(
        f"Candidates     : "
        f"{len(candidates)}"
    )

    print()


    # =====================================================
    # 결과
    # =====================================================

    profiles = []

    failed = []


    # =====================================================
    # 후보별 Profile 생성
    # =====================================================

    for index, candidate in enumerate(
        candidates,
        start=1
    ):

        company_name = (
            candidate.get(
                "company_name"
            )
        )

        corp_code = (
            candidate.get(
                "corp_code"
            )
        )

        stock_code = (
            candidate.get(
                "stock_code"
            )
        )


        # -------------------------------------------------
        # 08 cache
        # -------------------------------------------------

        cache_path = (
            CACHE_DIR
            / f"{corp_code}.json"
        )


        if not cache_path.exists():

            print(
                f"[WARN] "
                f"{company_name} "
                f"cache 없음"
            )

            failed.append({

                "company_name":
                    company_name,

                "corp_code":
                    corp_code,

                "stock_code":
                    stock_code,

                "reason":
                    "cache_not_found",
            })

            continue


        try:

            cache_data = (
                load_json(
                    cache_path
                )
            )

            business_text = (
                cache_data.get(
                    "business_text",
                    ""
                )
            )

            if not business_text:

                print(
                    f"[WARN] "
                    f"{company_name} "
                    f"business_text 없음"
                )

                failed.append({

                    "company_name":
                        company_name,

                    "corp_code":
                        corp_code,

                    "stock_code":
                        stock_code,

                    "reason":
                        "business_text_empty",
                })

                continue


            # ---------------------------------------------
            # 07과 동일한 company 구조
            # ---------------------------------------------

            company = (
                build_company_object(
                    candidate=
                        candidate,

                    analysis_as_of=
                        analysis_as_of,
                )
            )


            # ---------------------------------------------
            # source
            # ---------------------------------------------

            source = (
                build_source(
                    candidate
                )
            )


            # =============================================
            # 핵심
            #
            # 07에서 만든 동일 Profile Engine 호출
            # =============================================

            output = (
                profile_module
                .build_business_profile_from_text(

                    company=
                        company,

                    business_text=
                        business_text,

                    source=
                        source,

                    category_keywords=
                        category_keywords,

                    domain_name=
                        domain_name,

                    max_core_items=
                        40,
                )
            )


            # ---------------------------------------------
            # Candidate Pool 정보 추가
            # ---------------------------------------------

            output[
                "candidate_metadata"
            ] = {

                "market":
                    candidate.get(
                        "market"
                    ),

                "listing_date":
                    candidate.get(
                        "listing_date"
                    ),

                "listed_shares":
                    candidate.get(
                        "listed_shares"
                    ),

                "prefilter_score":
                    candidate.get(
                        "prefilter_score"
                    ),

                "industry_group_matches":
                    candidate.get(
                        "industry_group_matches",
                        {}
                    ),

                "business_group_matches":
                    candidate.get(
                        "business_group_matches",
                        {}
                    ),

                "source_filing":
                    candidate.get(
                        "source_filing"
                    ),
            }


            # ---------------------------------------------
            # 개별 저장
            # ---------------------------------------------

            company_output_path = (
                OUTPUT_DIR
                / f"{stock_code}.json"
            )

            save_json(
                company_output_path,
                output
            )

            profiles.append(
                output
            )


            # ---------------------------------------------
            # Summary
            # ---------------------------------------------

            profile = (
                output[
                    "business_profile"
                ]
            )

            print(
                f"[{index}/{len(candidates)}] "
                f"{company_name} | "
                f"company="
                f"{profile['company_evidence_count']} | "
                f"industry="
                f"{profile['industry_context_count']} | "
                f"core="
                f"{profile['core_evidence_count']}"
            )


        except Exception as e:

            print(
                f"[WARN] "
                f"{company_name} "
                f"처리 실패: {e}"
            )

            failed.append({

                "company_name":
                    company_name,

                "corp_code":
                    corp_code,

                "stock_code":
                    stock_code,

                "reason":
                    str(e),
            })


    # =====================================================
    # 전체 통합 파일
    # =====================================================

    combined_output = {

        "analysis_as_of":
            analysis_as_of,

        "profile_engine":
            str(
                SCRIPT_07_PATH
            ),

        "candidate_pool_source":
            str(
                CANDIDATE_POOL_PATH
            ),

        "profile_config": {

            "domain":
                domain_name,

            "max_core_items":
                40,
        },

        "stats": {

            "candidate_count":
                len(
                    candidates
                ),

            "profile_count":
                len(
                    profiles
                ),

            "failed_count":
                len(
                    failed
                ),
        },

        "failed":
            failed,

        "profiles":
            profiles,
    }


    save_json(
        OUTPUT_ALL_PATH,
        combined_output
    )


    # =====================================================
    # 완료
    # =====================================================

    print()

    print(
        "=" * 100
    )

    print(
        f"Candidate 수 : "
        f"{len(candidates)}"
    )

    print(
        f"Profile 생성 : "
        f"{len(profiles)}"
    )

    print(
        f"실패          : "
        f"{len(failed)}"
    )

    print()

    print(
        f"개별 Profile 저장: "
        f"{OUTPUT_DIR}"
    )

    print(
        f"통합 Profile 저장: "
        f"{OUTPUT_ALL_PATH}"
    )

    print(
        "=" * 100
    )


if __name__ == "__main__":
    main()