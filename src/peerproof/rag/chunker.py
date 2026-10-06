from __future__ import annotations

import hashlib
import re
from typing import Any


class ProfileRAGChunker:
    """
    profile_evidence.json을 RAG 검색용 chunk로 변환한다.

    개선점
    ------
    1. 긴 text evidence를 작은 검색 단위로 다시 분리
    2. DART 소제목 경계를 최대한 활용
    3. Markdown table은 하나의 단위로 보존
    4. 너무 긴 chunk는 길이 기준으로 추가 분할
    5. 중복 chunk 제거
    """

    CATEGORY_ORDER = [
        "business",
        "growth",
        "risk",
        "finance",
    ]

    MAX_CHARS = 900
    MIN_CHARS = 80
    OVERLAP_CHARS = 100

    # ========================================================
    # 기본 정규화
    # ========================================================

    @staticmethod
    def normalize_text(text: str) -> str:

        if not text:
            return ""

        text = text.replace("\xa0", " ")
        text = text.replace("\u200b", "")
        text = text.replace("\ufeff", "")
        text = text.replace("\t", " ")

        text = re.sub(
            r"[ ]{2,}",
            " ",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip()

    # ========================================================
    # fingerprint
    # ========================================================

    @classmethod
    def make_fingerprint(
        cls,
        text: str,
    ) -> str:

        normalized = cls.normalize_text(
            text
        ).lower()

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return hashlib.sha1(
            normalized.encode("utf-8")
        ).hexdigest()

    # ========================================================
    # 표인지 확인
    # ========================================================

    @staticmethod
    def is_table_block(
        text: str,
    ) -> bool:

        if "<!-- table_" in text:
            return True

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        if not lines:
            return False

        pipe_lines = sum(
            1
            for line in lines
            if "|" in line
        )

        return (
            pipe_lines
            >= max(
                2,
                len(lines) // 2,
            )
        )

    # ========================================================
    # DART 소제목 경계 판단
    # ========================================================

    @staticmethod
    def looks_like_heading(
        line: str,
    ) -> bool:

        line = line.strip()

        if not line:
            return False

        patterns = [
            r"^\d+\.\s*.+",
            r"^[가-힣]\.\s*.+",
            r"^\(\d+\)\s*.+",
            r"^[IVX]+\.\s*.+",
            r"^【.+】$",
        ]

        for pattern in patterns:

            if re.match(
                pattern,
                line,
            ):
                return True

        heading_keywords = [
            "주요 사업",
            "매출 및 수주",
            "판매경로",
            "판매방법",
            "위험관리",
            "연구개발",
            "생산 및 설비",
            "주요 제품",
            "원재료",
            "신규사업",
            "시장위험",
        ]

        return any(
            keyword in line
            and len(line) <= 80
            for keyword in heading_keywords
        )

    # ========================================================
    # 큰 text -> 의미 단위 분리
    # ========================================================

    @classmethod
    def split_semantic_blocks(
        cls,
        text: str,
    ) -> list[str]:

        text = cls.normalize_text(
            text
        )

        if not text:
            return []

        lines = text.splitlines()

        blocks = []
        current = []

        for line in lines:

            line = line.strip()

            if not line:
                continue

            # 새로운 소제목을 만나면
            # 기존 block 종료
            if (
                cls.looks_like_heading(line)
                and current
            ):

                block = "\n".join(
                    current
                ).strip()

                if block:
                    blocks.append(
                        block
                    )

                current = [line]

            else:

                current.append(
                    line
                )

        if current:

            block = "\n".join(
                current
            ).strip()

            if block:
                blocks.append(
                    block
                )

        return blocks

    # ========================================================
    # 너무 긴 블록 추가 분할
    # ========================================================

    @classmethod
    def split_by_length(
        cls,
        text: str,
    ) -> list[str]:

        text = cls.normalize_text(
            text
        )

        if len(text) <= cls.MAX_CHARS:
            return [text]

        # Markdown table이면
        # 최대한 표 자체를 보존
        if cls.is_table_block(
            text
        ):
            return [text]

        # 문장 기준 분리
        sentences = re.split(
            r"(?<=[.!?다요])\s+",
            text,
        )

        chunks = []
        current = ""

        for sentence in sentences:

            sentence = sentence.strip()

            if not sentence:
                continue

            candidate = (
                f"{current} {sentence}"
                if current
                else sentence
            )

            if (
                len(candidate)
                <= cls.MAX_CHARS
            ):

                current = candidate

            else:

                if current:
                    chunks.append(
                        current.strip()
                    )

                # 문장 하나가 너무 긴 경우
                if (
                    len(sentence)
                    > cls.MAX_CHARS
                ):

                    start = 0

                    while (
                        start
                        < len(sentence)
                    ):

                        end = (
                            start
                            + cls.MAX_CHARS
                        )

                        piece = sentence[
                            start:end
                        ].strip()

                        if piece:
                            chunks.append(
                                piece
                            )

                        start = (
                            end
                            - cls.OVERLAP_CHARS
                        )

                else:
                    current = sentence

        if current:
            chunks.append(
                current.strip()
            )

        return chunks

    # ========================================================
    # text evidence 최종 분할
    # ========================================================

    @classmethod
    def split_text_evidence(
        cls,
        text: str,
    ) -> list[str]:

        semantic_blocks = (
            cls.split_semantic_blocks(
                text
            )
        )

        final_chunks = []

        for block in semantic_blocks:

            split_chunks = (
                cls.split_by_length(
                    block
                )
            )

            for chunk in split_chunks:

                chunk = cls.normalize_text(
                    chunk
                )

                if (
                    len(chunk)
                    >= cls.MIN_CHARS
                ):
                    final_chunks.append(
                        chunk
                    )

        return final_chunks

    # ========================================================
    # Table 내용
    # ========================================================

    @classmethod
    def get_table_content(
        cls,
        evidence: dict[str, Any],
    ) -> str:

        markdown = evidence.get(
            "markdown",
            "",
        )

        if markdown:

            return cls.normalize_text(
                markdown
            )

        return cls.normalize_text(
            evidence.get(
                "content",
                "",
            )
        )

    # ========================================================
    # Chunk ID
    # ========================================================

    @staticmethod
    def make_chunk_id(
        category: str,
        report_type: str,
        source_type: str,
        index: int,
    ) -> str:

        return (
            f"{category}_"
            f"{report_type}_"
            f"{source_type}_"
            f"{index:04d}"
        )

    # ========================================================
    # 전체 chunk 생성
    # ========================================================

    @classmethod
    def build_chunks(
        cls,
        profile_evidence: dict[str, Any],
    ) -> dict[str, Any]:

        categories = (
            profile_evidence.get(
                "categories",
                {}
            )
        )

        chunks = []
        fingerprints = set()
        counters = {}

        duplicate_count = 0
        original_evidence_count = 0

        for category in cls.CATEGORY_ORDER:

            category_data = (
                categories.get(
                    category,
                    {}
                )
            )

            evidence_list = (
                category_data.get(
                    "evidence",
                    []
                )
            )

            for evidence in evidence_list:

                original_evidence_count += 1

                source_type = evidence.get(
                    "type",
                    "unknown",
                )

                report_type = evidence.get(
                    "report_type",
                    "unknown",
                )

                # ============================================
                # Table
                # ============================================

                if source_type == "table":

                    pieces = [
                        cls.get_table_content(
                            evidence
                        )
                    ]

                # ============================================
                # Text
                # ============================================

                else:

                    pieces = (
                        cls.split_text_evidence(
                            evidence.get(
                                "content",
                                "",
                            )
                        )
                    )

                # ============================================
                # 분리된 piece 각각 chunk화
                # ============================================

                for piece_index, content in enumerate(
                    pieces
                ):

                    content = cls.normalize_text(
                        content
                    )

                    if not content:
                        continue

                    fingerprint = (
                        cls.make_fingerprint(
                            content
                        )
                    )

                    if fingerprint in fingerprints:

                        duplicate_count += 1
                        continue

                    fingerprints.add(
                        fingerprint
                    )

                    key = (
                        category,
                        report_type,
                        source_type,
                    )

                    counters[key] = (
                        counters.get(
                            key,
                            0,
                        )
                        + 1
                    )

                    chunk_id = (
                        cls.make_chunk_id(
                            category=category,
                            report_type=report_type,
                            source_type=source_type,
                            index=counters[key],
                        )
                    )

                    chunk = {
                        "chunk_id": (
                            chunk_id
                        ),

                        "category": (
                            category
                        ),

                        "report_type": (
                            report_type
                        ),

                        "source_type": (
                            source_type
                        ),

                        "content": (
                            content
                        ),

                        "metadata": {
                            "table_id": (
                                evidence.get(
                                    "table_id"
                                )
                            ),

                            "block_index": (
                                evidence.get(
                                    "block_index"
                                )
                            ),

                            "piece_index": (
                                piece_index
                            ),

                            "matched_keywords": (
                                evidence.get(
                                    "matched_keywords",
                                    [],
                                )
                            ),

                            "retrieval_seed_score": (
                                evidence.get(
                                    "final_score",
                                    evidence.get(
                                        "score",
                                        0,
                                    ),
                                )
                            ),
                        },

                        "fingerprint": (
                            fingerprint
                        ),
                    }

                    chunks.append(
                        chunk
                    )

        # ====================================================
        # 통계
        # ====================================================

        statistics = {
            "original_evidence_count": (
                original_evidence_count
            ),

            "total_chunks": (
                len(chunks)
            ),

            "duplicates_removed": (
                duplicate_count
            ),

            "by_category": {},

            "by_source_type": {},

            "by_report_type": {},
        }

        for chunk in chunks:

            category = chunk[
                "category"
            ]

            source_type = chunk[
                "source_type"
            ]

            report_type = chunk[
                "report_type"
            ]

            statistics[
                "by_category"
            ][category] = (
                statistics[
                    "by_category"
                ].get(
                    category,
                    0,
                )
                + 1
            )

            statistics[
                "by_source_type"
            ][source_type] = (
                statistics[
                    "by_source_type"
                ].get(
                    source_type,
                    0,
                )
                + 1
            )

            statistics[
                "by_report_type"
            ][report_type] = (
                statistics[
                    "by_report_type"
                ].get(
                    report_type,
                    0,
                )
                + 1
            )

        return {
            "company": (
                profile_evidence.get(
                    "company",
                    {}
                )
            ),

            "rag_version": "0.2",

            "chunk_strategy": {
                "source": (
                    "profile_evidence"
                ),

                "semantic_split": True,

                "heading_split": True,

                "max_chars": (
                    cls.MAX_CHARS
                ),

                "min_chars": (
                    cls.MIN_CHARS
                ),

                "overlap_chars": (
                    cls.OVERLAP_CHARS
                ),

                "table_strategy": (
                    "preserve markdown table"
                ),

                "deduplication": (
                    "sha1 normalized content"
                ),
            },

            "statistics": (
                statistics
            ),

            "chunks": (
                chunks
            ),
        }