from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schema import (
    CATEGORY_KEYWORDS,
    PROFILE_SCHEMA,
    REPORT_PRIORITY,
)


class ProfileEvidenceExtractor:
    """
    DART 전처리 결과에서
    Business / Growth / Risk / Finance 관련
    문단과 표를 찾아 근거 후보를 생성한다.
    """

    def __init__(
        self,
        company_dir: str | Path,
    ):
        self.company_dir = Path(
            company_dir
        )

        self.report_types = [
            "annual",
            "semiannual",
            "quarterly",
        ]

    # ========================================================
    # 파일 읽기
    # ========================================================

    @staticmethod
    def load_text(
        path: Path,
    ) -> str:

        if not path.exists():
            return ""

        return path.read_text(
            encoding="utf-8"
        )

    @staticmethod
    def load_json(
        path: Path,
    ):

        if not path.exists():
            return []

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    # ========================================================
    # 정규화
    # ========================================================

    @staticmethod
    def normalize(
        text: str,
    ) -> str:

        text = text.replace(
            "\xa0",
            " ",
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # ========================================================
    # document.md -> 검색 블록
    # ========================================================

    def split_document_blocks(
        self,
        text: str,
        max_chars: int = 1800,
    ) -> list[str]:
        """
        document.md를 너무 길지 않은
        검색 단위로 나눈다.

        우선 빈 줄 기준으로 문단을 합치되
        max_chars를 넘으면 새 블록 생성.
        """

        paragraphs = [
            self.normalize(p)
            for p in re.split(
                r"\n\s*\n",
                text,
            )
            if self.normalize(p)
        ]

        blocks = []

        current = ""

        for paragraph in paragraphs:

            # Markdown 표는 하나의 블록처럼 유지
            if paragraph.startswith("|"):

                if current:
                    blocks.append(
                        current
                    )

                    current = ""

                blocks.append(
                    paragraph
                )

                continue

            if not current:

                current = paragraph

                continue

            candidate = (
                current
                + "\n"
                + paragraph
            )

            if len(candidate) <= max_chars:

                current = candidate

            else:

                blocks.append(
                    current
                )

                current = paragraph

        if current:

            blocks.append(
                current
            )

        return blocks

    # ========================================================
    # 키워드 점수
    # ========================================================

    @staticmethod
    def keyword_score(
        text: str,
        keywords: list[str],
    ) -> tuple[int, list[str]]:

        lower_text = (
            text.lower()
        )

        matched = []

        for keyword in keywords:

            if keyword.lower() in lower_text:

                matched.append(
                    keyword
                )

        return (
            len(matched),
            matched,
        )

    # ========================================================
    # 문단 evidence
    # ========================================================

    def extract_text_evidence(
        self,
        report_type: str,
        category: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:

        document_path = (
            self.company_dir
            / report_type
            / "document.md"
        )

        text = self.load_text(
            document_path
        )

        if not text:
            return []

        blocks = (
            self.split_document_blocks(
                text
            )
        )

        keywords = (
            CATEGORY_KEYWORDS[
                category
            ]
        )

        candidates = []

        for index, block in enumerate(
            blocks
        ):

            score, matched = (
                self.keyword_score(
                    block,
                    keywords,
                )
            )

            if score == 0:
                continue

            candidates.append(
                {
                    "type": "text",
                    "report_type": report_type,
                    "block_index": index,
                    "score": score,
                    "matched_keywords": matched,
                    "content": block,
                }
            )

        candidates.sort(
            key=lambda item: (
                item["score"],
                len(
                    item["content"]
                ),
            ),
            reverse=True,
        )

        return candidates[
            :limit
        ]

    # ========================================================
    # 표 -> 검색용 텍스트
    # ========================================================

    @staticmethod
    def table_to_search_text(
        table: dict,
    ) -> str:

        parts = []

        for row in table.get(
            "rows",
            [],
        ):

            values = []

            for cell in row:

                text = (
                    cell.get(
                        "text",
                        "",
                    )
                )

                if text:
                    values.append(
                        text
                    )

            if values:

                parts.append(
                    " | ".join(
                        values
                    )
                )

        return "\n".join(
            parts
        )

    # ========================================================
    # 표 evidence
    # ========================================================

    def extract_table_evidence(
        self,
        report_type: str,
        category: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:

        tables_path = (
            self.company_dir
            / report_type
            / "tables.json"
        )

        tables = self.load_json(
            tables_path
        )

        if not tables:
            return []

        keywords = (
            CATEGORY_KEYWORDS[
                category
            ]
        )

        candidates = []

        for table in tables:

            search_text = (
                self.table_to_search_text(
                    table
                )
            )

            score, matched = (
                self.keyword_score(
                    search_text,
                    keywords,
                )
            )

            if score == 0:
                continue

            candidates.append(
                {
                    "type": "table",
                    "report_type": report_type,
                    "table_id": table.get(
                        "table_id"
                    ),
                    "score": score,
                    "matched_keywords": matched,
                    "content": search_text,
                    "markdown": table.get(
                        "markdown",
                        "",
                    ),
                }
            )

        candidates.sort(
            key=lambda item: (
                item["score"],
                len(
                    item["content"]
                ),
            ),
            reverse=True,
        )

        return candidates[
            :limit
        ]

    # ========================================================
    # report priority 보정
    # ========================================================

    @staticmethod
    def priority_weight(
        category: str,
        report_type: str,
    ) -> float:

        priorities = (
            REPORT_PRIORITY[
                category
            ]
        )

        try:

            index = priorities.index(
                report_type
            )

        except ValueError:

            return 1.0

        weights = [
            1.30,
            1.15,
            1.00,
        ]

        return weights[
            index
        ]

    # ========================================================
    # 카테고리 evidence 생성
    # ========================================================

    def extract_category(
        self,
        category: str,
        text_limit: int = 15,
        table_limit: int = 15,
        final_limit: int = 25,
    ) -> dict[str, Any]:

        all_evidence = []

        for report_type in (
            self.report_types
        ):

            text_candidates = (
                self.extract_text_evidence(
                    report_type,
                    category,
                    text_limit,
                )
            )

            table_candidates = (
                self.extract_table_evidence(
                    report_type,
                    category,
                    table_limit,
                )
            )

            candidates = (
                text_candidates
                + table_candidates
            )

            weight = (
                self.priority_weight(
                    category,
                    report_type,
                )
            )

            for item in candidates:

                item[
                    "raw_score"
                ] = item[
                    "score"
                ]

                item[
                    "priority_weight"
                ] = weight

                item[
                    "final_score"
                ] = round(
                    item[
                        "raw_score"
                    ]
                    * weight,
                    4,
                )

                all_evidence.append(
                    item
                )

        all_evidence.sort(
            key=lambda item: (
                item[
                    "final_score"
                ],
                item[
                    "raw_score"
                ],
            ),
            reverse=True,
        )

        return {
            "description": (
                PROFILE_SCHEMA[
                    category
                ][
                    "description"
                ]
            ),
            "target_fields": (
                PROFILE_SCHEMA[
                    category
                ][
                    "fields"
                ]
            ),
            "evidence": (
                all_evidence[
                    :final_limit
                ]
            ),
        }

    # ========================================================
    # 전체 Profile Evidence
    # ========================================================

    def build(
        self,
        company_metadata: dict | None = None,
    ) -> dict[str, Any]:

        result = {
            "company": (
                company_metadata
                or {}
            ),
            "profile_version": "0.1",
            "stage": (
                "evidence_extraction"
            ),
            "categories": {},
        }

        for category in (
            "business",
            "growth",
            "risk",
            "finance",
        ):

            result[
                "categories"
            ][
                category
            ] = (
                self.extract_category(
                    category
                )
            )

        return result