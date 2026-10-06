from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from peerproof.profile.schema import (
    PROFILE_SCHEMA,
    get_profile_field_count,
)

from peerproof.profile.llm_client import (
    ProfileLLMClient,
)


# ============================================================
# Company Profile Builder
# ============================================================

class CompanyProfileBuilder:

    def __init__(
        self,
        retriever,
        llm_client: ProfileLLMClient,
        query_top_k: int = 3,
        evidence_limit: int = 8,
    ):

        self.retriever = retriever
        self.llm_client = llm_client

        # query × category 하나당 검색 개수
        self.query_top_k = query_top_k

        # Gemini에 전달하는 최대 Evidence 개수
        self.evidence_limit = evidence_limit

    # ========================================================
    # JSON
    # ========================================================

    @staticmethod
    def load_json(
        path: Path,
    ) -> dict[str, Any]:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    @staticmethod
    def save_json(
        path: Path,
        data: Any,
    ) -> None:

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            path,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

    # ========================================================
    # Retriever
    # ========================================================

    def _search(
        self,
        query: str,
        category: str,
    ) -> list[dict[str, Any]]:

        results = self.retriever.search(
            query=query,
            top_k=self.query_top_k,
            category=category,
        )

        if results is None:
            return []

        return list(results)

    # ========================================================
    # Search result normalize
    # ========================================================

    @staticmethod
    def _normalize_search_result(
        result: dict[str, Any],
        query: str,
        retrieval_category: str,
    ) -> dict[str, Any]:

        # ----------------------------------------------------
        # content
        # ----------------------------------------------------

        content = (
            result.get("content")
            or result.get("text")
            or result.get("chunk")
            or ""
        )

        # ----------------------------------------------------
        # chunk id
        # ----------------------------------------------------

        chunk_id = (
            result.get("chunk_id")
            or result.get("id")
        )

        if not chunk_id:

            normalized = " ".join(
                str(content).split()
            )

            chunk_id = hashlib.sha1(
                normalized.encode("utf-8")
            ).hexdigest()[:16]

        # ----------------------------------------------------
        # score
        # ----------------------------------------------------

        score = result.get("score")

        if score is None:
            score = result.get("similarity")

        if score is None:
            score = 0.0

        # ----------------------------------------------------
        # metadata
        # ----------------------------------------------------

        metadata = (
            result.get("metadata")
            or {}
        )

        report = (
            result.get("report")
            or result.get("source")
            or metadata.get("report")
            or metadata.get("report_type")
            or metadata.get("source")
        )

        section = (
            result.get("section")
            or metadata.get("section")
            or metadata.get("heading")
        )

        page = (
            result.get("page")
            or metadata.get("page")
            or metadata.get("page_number")
        )

        return {
            "chunk_id": str(chunk_id),

            "content": str(content),

            "score": float(score),

            "report": report,

            "section": section,

            "page": page,

            "metadata": metadata,

            # 어떤 질문에서 검색됐는가
            "matched_queries": [
                query
            ],

            # 어떤 category에서 검색됐는가
            "matched_categories": [
                retrieval_category
            ],

            "query_hits": 1,

            "category_hits": 1,
        }

    # ========================================================
    # Multiple Query + Multiple Category Retrieval
    # ========================================================

    def retrieve_field_evidence(
        self,
        category: str,
        field_config: dict[str, Any],
    ) -> list[dict[str, Any]]:

        queries = field_config.get(
            "queries",
            [],
        )

        # schema에 명시된 검색 category 사용
        retrieval_categories = (
            field_config.get(
                "retrieval_categories"
            )
            or [category]
        )

        print(
            "      검색 categories: "
            + ", ".join(
                retrieval_categories
            )
        )

        merged: dict[
            str,
            dict[str, Any],
        ] = {}

        # ====================================================
        # Query
        # ====================================================

        for query_index, query in enumerate(
            queries,
            start=1,
        ):

            print()
            print(
                f"      Query "
                f"{query_index}/{len(queries)}"
            )

            print(
                f"      → {query}"
            )

            # ================================================
            # Category
            # ================================================

            for retrieval_category in (
                retrieval_categories
            ):

                results = self._search(
                    query=query,
                    category=retrieval_category,
                )

                print(
                    f"        "
                    f"[{retrieval_category}] "
                    f"retrieved: "
                    f"{len(results)}"
                )

                # ============================================
                # Search results
                # ============================================

                for result in results:

                    item = (
                        self._normalize_search_result(
                            result=result,
                            query=query,
                            retrieval_category=(
                                retrieval_category
                            ),
                        )
                    )

                    chunk_id = item[
                        "chunk_id"
                    ]

                    # ========================================
                    # 처음 등장한 chunk
                    # ========================================

                    if chunk_id not in merged:

                        merged[
                            chunk_id
                        ] = item

                        continue

                    # ========================================
                    # 이미 검색된 chunk
                    # ========================================

                    existing = merged[
                        chunk_id
                    ]

                    # ----------------------------------------
                    # Query
                    # ----------------------------------------

                    if query not in (
                        existing[
                            "matched_queries"
                        ]
                    ):

                        existing[
                            "matched_queries"
                        ].append(
                            query
                        )

                        existing[
                            "query_hits"
                        ] += 1

                    # ----------------------------------------
                    # Category
                    # ----------------------------------------

                    if retrieval_category not in (
                        existing[
                            "matched_categories"
                        ]
                    ):

                        existing[
                            "matched_categories"
                        ].append(
                            retrieval_category
                        )

                        existing[
                            "category_hits"
                        ] += 1

                    # 동일 chunk가 여러 번 잡혔다면
                    # 가장 높은 semantic score 유지
                    existing[
                        "score"
                    ] = max(
                        existing[
                            "score"
                        ],
                        item[
                            "score"
                        ],
                    )

        # ====================================================
        # Evidence ranking
        # ====================================================

        evidence_list = []

        for item in merged.values():

            # 여러 query에서 반복적으로 검색되면
            # 조금 가산점
            query_bonus = (
                0.03
                * max(
                    item[
                        "query_hits"
                    ] - 1,
                    0,
                )
            )

            # 여러 category에서도 검색되었다면
            # 관련성이 반복 확인된 것으로 보고
            # 작은 가산점
            category_bonus = (
                0.01
                * max(
                    item[
                        "category_hits"
                    ] - 1,
                    0,
                )
            )

            item[
                "fused_score"
            ] = (
                item["score"]
                + query_bonus
                + category_bonus
            )

            evidence_list.append(
                item
            )

        # 높은 점수 순
        evidence_list.sort(
            key=lambda item: (
                item[
                    "fused_score"
                ]
            ),
            reverse=True,
        )

        # Gemini 입력 제한
        evidence_list = (
            evidence_list[
                : self.evidence_limit
            ]
        )

        # ====================================================
        # Evidence ID
        # ====================================================

        for index, item in enumerate(
            evidence_list,
            start=1,
        ):

            item[
                "evidence_id"
            ] = f"E{index}"

        return evidence_list

    # ========================================================
    # LLM Evidence → 실제 Evidence 연결
    # ========================================================

    @staticmethod
    def resolve_evidence(
        evidences: list[dict[str, Any]],
        selected_ids: list[str],
    ) -> list[dict[str, Any]]:

        evidence_map = {
            evidence[
                "evidence_id"
            ]: evidence
            for evidence in evidences
        }

        resolved = []

        for evidence_id in (
            selected_ids
        ):

            evidence = (
                evidence_map.get(
                    evidence_id
                )
            )

            if not evidence:
                continue

            resolved.append(
                {
                    "evidence_id": (
                        evidence_id
                    ),

                    "chunk_id": (
                        evidence.get(
                            "chunk_id"
                        )
                    ),

                    "report": (
                        evidence.get(
                            "report"
                        )
                    ),

                    "page": (
                        evidence.get(
                            "page"
                        )
                    ),

                    "section": (
                        evidence.get(
                            "section"
                        )
                    ),

                    "content": (
                        evidence.get(
                            "content"
                        )
                    ),

                    "score": (
                        evidence.get(
                            "score"
                        )
                    ),

                    "fused_score": (
                        evidence.get(
                            "fused_score"
                        )
                    ),

                    "matched_queries": (
                        evidence.get(
                            "matched_queries"
                        )
                    ),

                    "matched_categories": (
                        evidence.get(
                            "matched_categories"
                        )
                    ),
                }
            )

        return resolved

    # ========================================================
    # 하나의 field 생성
    # ========================================================

    def build_field(
        self,
        category: str,
        field_name: str,
        field_config: dict[str, Any],
    ) -> dict[str, Any]:

        print()

        print(
            f"    "
            f"[{field_config.get('code')}] "
            f"{field_config.get('label')}"
        )

        # ====================================================
        # 1. Multiple-query / Multi-category RAG
        # ====================================================

        evidences = (
            self.retrieve_field_evidence(
                category=category,
                field_config=field_config,
            )
        )

        print()
        print(
            f"      통합 evidence: "
            f"{len(evidences)}"
        )

        # ====================================================
        # 2. Gemini
        # ====================================================

        llm_result = (
            self.llm_client
            .generate_profile_field(
                category=category,
                field_name=field_name,
                field_config=field_config,
                evidences=evidences,
            )
        )

        # ====================================================
        # 3. Gemini가 선택한 Evidence 연결
        # ====================================================

        selected_ids = (
            llm_result.get(
                "evidence_ids"
            )
            or []
        )

        selected_evidence = (
            self.resolve_evidence(
                evidences=evidences,
                selected_ids=selected_ids,
            )
        )

        # ====================================================
        # 4. 결과
        # ====================================================

        return {
            "code": (
                field_config.get(
                    "code"
                )
            ),

            "label": (
                field_config.get(
                    "label"
                )
            ),

            "value": (
                llm_result.get(
                    "value"
                )
            ),

            "status": (
                llm_result.get(
                    "status"
                )
            ),

            "company_claim": (
                llm_result.get(
                    "company_claim"
                )
            ),

            "interpretation": (
                llm_result.get(
                    "interpretation"
                )
            ),

            "reason": (
                llm_result.get(
                    "reason"
                )
            ),

            "retrieval_categories": (
                field_config.get(
                    "retrieval_categories",
                    [category],
                )
            ),

            "queries": (
                field_config.get(
                    "queries",
                    []
                )
            ),

            "rules": (
                field_config.get(
                    "rules",
                    []
                )
            ),

            # Gemini가 최종 선택한 Evidence
            "evidence": (
                selected_evidence
            ),

            # 검색된 전체 Evidence
            # 디버깅용으로 반드시 남긴다.
            "retrieved_evidence": (
                evidences
            ),
        }

    # ========================================================
    # 완료 여부
    # ========================================================

    @staticmethod
    def _is_completed_field(
        value: Any,
    ) -> bool:

        if not isinstance(
            value,
            dict,
        ):
            return False

        status = value.get(
            "status"
        )

        return status in {
            "확인",
            "부분확인",
            "미공시",
            "해당없음",
        }

    # ========================================================
    # 전체 Profile 생성
    # ========================================================

    def build_profile(
        self,
        company_name: str,
        output_path: Path,
        resume: bool = True,
        target_categories: list[str] | None = None,
    ) -> dict[str, Any]:

        # ====================================================
        # 기존 파일 로드
        # ====================================================

        if (
            resume
            and output_path.exists()
        ):

            profile = (
                self.load_json(
                    output_path
                )
            )

            print()
            print(
                "기존 v2 Profile 발견 "
                "→ 이어서 실행"
            )

        else:

            profile = {
                "version": "2.0",

                "company": (
                    company_name
                ),

                "profile": {
                    "business": {},
                    "growth": {},
                    "risk": {},
                },

                "finance": {
                    "status": (
                        "separate_pipeline"
                    ),

                    "description": (
                        "Finance는 LLM이 아니라 "
                        "DART 재무 API와 "
                        "Python 계산으로 처리한다."
                    ),
                },
            }

        total_fields = (
            get_profile_field_count()
        )

        success_count = 0
        skip_count = 0
        fail_count = 0

        selected_field_count = 0

        # ====================================================
        # Category
        # ====================================================

        for category, fields in (
            PROFILE_SCHEMA.items()
        ):

            # 선택된 category만 실행
            if (
                target_categories is not None
                and category
                not in target_categories
            ):
                continue

            print()
            print(
                "=" * 70
            )

            print(
                category.upper()
            )

            print(
                "=" * 70
            )

            profile[
                "profile"
            ].setdefault(
                category,
                {},
            )

            # =================================================
            # Field
            # =================================================

            for field_name, field_config in (
                fields.items()
            ):

                selected_field_count += 1

                print()
                print(
                    f"[{selected_field_count}/"
                    f"{total_fields}] "
                    f"{category}."
                    f"{field_name}"
                )

                existing = (
                    profile[
                        "profile"
                    ][
                        category
                    ].get(
                        field_name
                    )
                )

                # =============================================
                # Resume
                # =============================================

                if (
                    resume
                    and self._is_completed_field(
                        existing
                    )
                ):

                    print(
                        "    SKIP "
                        "(이미 완료)"
                    )

                    skip_count += 1

                    continue

                try:

                    result = (
                        self.build_field(
                            category=category,
                            field_name=field_name,
                            field_config=field_config,
                        )
                    )

                    profile[
                        "profile"
                    ][
                        category
                    ][
                        field_name
                    ] = result

                    success_count += 1

                    print(
                        f"    → "
                        f"{result['status']}"
                    )

                    if result.get(
                        "value"
                    ):

                        print(
                            f"    → "
                            f"{result['value']}"
                        )

                except Exception as error:

                    fail_count += 1

                    print(
                        f"    [FAILED] "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )

                    profile[
                        "profile"
                    ][
                        category
                    ][
                        field_name
                    ] = {
                        "code": (
                            field_config.get(
                                "code"
                            )
                        ),

                        "label": (
                            field_config.get(
                                "label"
                            )
                        ),

                        "status": (
                            "error"
                        ),

                        "value": None,

                        "error": str(
                            error
                        ),
                    }

                # 필드 하나 끝날 때마다 저장
                self.save_json(
                    output_path,
                    profile,
                )

        # ====================================================
        # Summary
        # ====================================================

        profile[
            "summary"
        ] = {
            "total_fields": (
                total_fields
            ),

            "selected_fields": (
                selected_field_count
            ),

            "success": (
                success_count
            ),

            "skipped": (
                skip_count
            ),

            "failed": (
                fail_count
            ),
        }

        self.save_json(
            output_path,
            profile,
        )

        return profile