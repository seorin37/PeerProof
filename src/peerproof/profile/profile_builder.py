from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from peerproof.profile.llm_client import (
    ProfileLLMClient,
)

from peerproof.rag.retriever import (
    ProfileRetriever,
)


PROFILE_FIELDS = {

    # ======================================================
    # BUSINESS
    # ======================================================

    "business": {

        "products_services": (
            "이 기업의 주요 사업부문, "
            "제품, 서비스 및 브랜드는 무엇인가?"
        ),

        "revenue_model": (
            "이 기업은 어떤 제품이나 서비스를 "
            "어떤 방식으로 판매하여 "
            "매출을 발생시키는가?"
        ),

        "customer_type": (
            "이 기업의 주요 고객 유형은 누구인가? "
            "최종 소비자, 기업 고객, 해외 고객 등 "
            "공시 근거를 바탕으로 설명하라."
        ),

        "distribution_channel": (
            "이 기업의 주요 판매 및 "
            "유통 채널은 무엇인가?"
        ),

        "business_structure": (
            "이 기업의 주요 사업부문과 "
            "사업 운영 구조는 "
            "어떻게 구성되어 있는가?"
        ),
    },

    # ======================================================
    # GROWTH
    # ======================================================

    "growth": {

        "revenue_growth": (
            "이 기업의 매출 성장 추세와 "
            "성장 특징은 무엇인가?"
        ),

        "global_expansion": (
            "이 기업의 해외 진출 및 "
            "글로벌 사업 확장 현황은 무엇인가?"
        ),

        "new_business": (
            "이 기업이 추진하고 있는 "
            "신규 사업, 신규 제품 또는 "
            "사업영역 확장은 무엇인가?"
        ),

        "capacity_expansion": (
            "이 기업의 생산능력 확대, "
            "시설 투자 또는 생산 내재화 "
            "현황은 무엇인가?"
        ),
    },

    # ======================================================
    # RISK
    # ======================================================

    "risk": {

        "customer_concentration": (
            "특정 고객, 거래처 또는 "
            "판매채널에 대한 의존도가 "
            "높은 위험이 있는가?"
        ),

        "competition_risk": (
            "이 기업이 직면한 "
            "주요 경쟁 위험은 무엇인가?"
        ),

        "regulatory_risk": (
            "이 기업의 사업과 관련된 "
            "주요 규제 또는 "
            "법적 위험은 무엇인가?"
        ),

        "supply_chain_risk": (
            "원재료, 외주생산, 공급업체 등과 "
            "관련된 공급망 위험은 무엇인가?"
        ),
    },
}


class CompanyProfileBuilder:

    def __init__(
        self,
        retriever: ProfileRetriever,
        llm_client: ProfileLLMClient,
        top_k: int = 5,
    ):

        self.retriever = retriever
        self.llm_client = llm_client
        self.top_k = top_k

    # ======================================================
    # JSON 저장
    # ======================================================

    @staticmethod
    def _save_json(
        path: Path,
        data: dict[str, Any],
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

    # ======================================================
    # 기존 Profile 로드
    # ======================================================

    @staticmethod
    def _load_existing_profile(
        path: Path,
    ) -> dict[str, Any] | None:

        if not path.exists():
            return None

        try:

            with open(
                path,
                "r",
                encoding="utf-8",
            ) as file:

                return json.load(
                    file
                )

        except Exception:

            return None

    # ======================================================
    # 성공한 field인지 판단
    # ======================================================

    @staticmethod
    def _is_completed_field(
        field_data: Any,
    ) -> bool:

        if not isinstance(
            field_data,
            dict,
        ):
            return False

        # 이전 실패 결과
        if field_data.get(
            "error"
        ):
            return False

        # value key 자체가 있어야 함
        if "value" not in field_data:
            return False

        value = field_data.get(
            "value"
        )

        # null도 "근거 없음"이라는
        # 정상적인 LLM 판단일 수 있음
        #
        # reason + evidence_ids 구조가 있으면
        # 정상 처리된 것으로 본다.
        if (
            "reason" in field_data
            and "evidence_ids"
            in field_data
        ):
            return True

        return (
            value is not None
        )

    # ======================================================
    # 초기 Profile
    # ======================================================

    @staticmethod
    def _create_empty_profile(
        company_name: str,
    ) -> dict[str, Any]:

        return {
            "company": company_name,

            "profile_version": "0.2",

            "generation_method": (
                "DART + BGE-M3 RAG + LLM"
            ),

            "business": {},

            "growth": {},

            "risk": {},

            "finance": {
                "status": (
                    "not_generated"
                )
            },
        }

    # ======================================================
    # Field 하나 생성
    # ======================================================

    def build_field(
        self,
        company_name: str,
        category: str,
        field_name: str,
        question: str,
    ) -> dict[str, Any]:

        # --------------------------------------------------
        # RAG
        # --------------------------------------------------

        evidence = (
            self.retriever.search(
                query=question,
                top_k=self.top_k,
                category=category,
            )
        )

        if not evidence:

            return {
                "question": question,

                "value": None,

                "evidence_ids": [],

                "reason": (
                    "관련 DART 근거를 "
                    "검색하지 못했습니다."
                ),

                "retrieved_evidence": [],
            }

        # --------------------------------------------------
        # LLM
        # --------------------------------------------------

        llm_result = (
            self.llm_client
            .extract_field(
                company_name=(
                    company_name
                ),
                field_name=(
                    field_name
                ),
                question=question,
                evidence=evidence,
            )
        )

        # --------------------------------------------------
        # 저장 구조
        # --------------------------------------------------

        return {
            "question": question,

            "value": (
                llm_result.get(
                    "value"
                )
            ),

            "evidence_ids": (
                llm_result.get(
                    "evidence_ids",
                    [],
                )
            ),

            "reason": (
                llm_result.get(
                    "reason"
                )
            ),

            "retrieved_evidence": [
                {
                    "chunk_id": (
                        item[
                            "chunk_id"
                        ]
                    ),

                    "score": float(
                        item[
                            "score"
                        ]
                    ),

                    "report_type": (
                        item[
                            "report_type"
                        ]
                    ),

                    "source_type": (
                        item[
                            "source_type"
                        ]
                    ),
                }
                for item
                in evidence
            ],
        }

    # ======================================================
    # 전체 Profile 생성
    # ======================================================

    def build_profile(
        self,
        company_name: str,
        output_path: Path,
        resume: bool = True,
    ) -> dict[str, Any]:

        # --------------------------------------------------
        # 기존 파일이 있으면 이어서 진행
        # --------------------------------------------------

        existing = None

        if resume:

            existing = (
                self._load_existing_profile(
                    output_path
                )
            )

        if existing:

            profile = existing

            print()
            print(
                "기존 company_profile.json "
                "발견"
            )

            print(
                "성공한 필드는 건너뛰고 "
                "실패한 필드부터 재개합니다."
            )

        else:

            profile = (
                self._create_empty_profile(
                    company_name
                )
            )

        # 구조 안전장치
        profile[
            "company"
        ] = company_name

        profile[
            "profile_version"
        ] = "0.2"

        profile[
            "generation_method"
        ] = (
            "DART + BGE-M3 RAG + LLM"
        )

        profile.setdefault(
            "business",
            {},
        )

        profile.setdefault(
            "growth",
            {},
        )

        profile.setdefault(
            "risk",
            {},
        )

        profile.setdefault(
            "finance",
            {
                "status": (
                    "not_generated"
                )
            },
        )

        # --------------------------------------------------
        # 전체 field 개수
        # --------------------------------------------------

        total_fields = sum(
            len(fields)
            for fields
            in PROFILE_FIELDS.values()
        )

        current = 0

        success_count = 0
        skipped_count = 0
        failed_count = 0

        # --------------------------------------------------
        # category 반복
        # --------------------------------------------------

        for (
            category,
            fields,
        ) in PROFILE_FIELDS.items():

            for (
                field_name,
                question,
            ) in fields.items():

                current += 1

                print()
                print(
                    "=" * 70
                )

                print(
                    f"[{current}/"
                    f"{total_fields}] "
                    f"{category}."
                    f"{field_name}"
                )

                print(
                    "=" * 70
                )

                # ------------------------------------------
                # 기존 성공 결과 확인
                # ------------------------------------------

                existing_field = (
                    profile
                    .get(
                        category,
                        {},
                    )
                    .get(
                        field_name
                    )
                )

                if (
                    resume
                    and self._is_completed_field(
                        existing_field
                    )
                ):

                    skipped_count += 1

                    print(
                        "이미 정상 생성된 "
                        "필드입니다."
                    )

                    print(
                        "→ SKIP"
                    )

                    print(
                        "value: "
                        f"{existing_field.get('value')}"
                    )

                    continue

                print(
                    f"질문: {question}"
                )

                # ------------------------------------------
                # 생성
                # ------------------------------------------

                try:

                    result = (
                        self.build_field(
                            company_name=(
                                company_name
                            ),
                            category=(
                                category
                            ),
                            field_name=(
                                field_name
                            ),
                            question=(
                                question
                            ),
                        )
                    )

                    profile[
                        category
                    ][field_name] = result

                    success_count += 1

                    print()
                    print(
                        "완료"
                    )

                    print(
                        "value: "
                        f"{result['value']}"
                    )

                    if (
                        result[
                            "evidence_ids"
                        ]
                    ):

                        print(
                            "evidence:"
                        )

                        for evidence_id in (
                            result[
                                "evidence_ids"
                            ]
                        ):

                            print(
                                f"  - "
                                f"{evidence_id}"
                            )

                except Exception as error:

                    failed_count += 1

                    print()
                    print(
                        f"ERROR: {error}"
                    )

                    profile[
                        category
                    ][field_name] = {
                        "question": question,

                        "value": None,

                        "evidence_ids": [],

                        "reason": None,

                        "retrieved_evidence": [],

                        "error": str(
                            error
                        ),
                    }

                # ------------------------------------------
                # 핵심:
                # field 하나 끝날 때마다 저장
                # ------------------------------------------

                self._save_json(
                    output_path,
                    profile,
                )

                print(
                    "중간 저장 완료"
                )

        # --------------------------------------------------
        # 최종 저장
        # --------------------------------------------------

        self._save_json(
            output_path,
            profile,
        )

        print()
        print(
            "=" * 70
        )

        print(
            "PROFILE BUILD SUMMARY"
        )

        print(
            "=" * 70
        )

        print(
            f"신규 성공 : "
            f"{success_count}"
        )

        print(
            f"기존 SKIP : "
            f"{skipped_count}"
        )

        print(
            f"실패      : "
            f"{failed_count}"
        )

        print(
            f"전체      : "
            f"{total_fields}"
        )

        return profile