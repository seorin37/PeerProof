from __future__ import annotations

from typing import Any

import numpy as np

from .embedder import BGEM3Embedder


class ProfileRetriever:
    """
    PeerProof Business Profile용 RAG Retriever.

    BGE-M3 dense embedding +
    cosine similarity 기반 Top-k 검색.
    """

    def __init__(
        self,
        chunks: list[dict[str, Any]],
        embeddings: np.ndarray,
        embedder: BGEM3Embedder,
    ):

        if len(chunks) != len(
            embeddings
        ):
            raise ValueError(
                "chunk 개수와 embedding 개수가 다릅니다.\n"
                f"chunks={len(chunks)}, "
                f"embeddings={len(embeddings)}"
            )

        self.chunks = chunks
        self.embeddings = embeddings
        self.embedder = embedder

    # ======================================================
    # 검색
    # ======================================================

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
        source_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        query와 가장 유사한 chunk Top-k 반환.

        category:
            business / growth / risk / finance

        source_type:
            text / table
        """

        query_embedding = (
            self.embedder.encode_query(
                query
            )
        )

        candidate_indexes = []

        # --------------------------------------------------
        # metadata filter
        # --------------------------------------------------

        for index, chunk in enumerate(
            self.chunks
        ):

            if (
                category is not None
                and chunk.get(
                    "category"
                )
                != category
            ):
                continue

            if (
                source_type is not None
                and chunk.get(
                    "source_type"
                )
                != source_type
            ):
                continue

            candidate_indexes.append(
                index
            )

        if not candidate_indexes:

            return []

        candidate_embeddings = (
            self.embeddings[
                candidate_indexes
            ]
        )

        # --------------------------------------------------
        # cosine similarity
        # --------------------------------------------------
        #
        # document/query 모두 normalize 되어 있으므로
        # dot product = cosine similarity
        #

        scores = (
            candidate_embeddings
            @ query_embedding
        )

        order = np.argsort(
            scores
        )[::-1]

        top_k = min(
            top_k,
            len(order),
        )

        results = []

        for rank, position in enumerate(
            order[:top_k],
            start=1,
        ):

            original_index = (
                candidate_indexes[
                    position
                ]
            )

            chunk = self.chunks[
                original_index
            ]

            result = {
                "rank": rank,

                "score": float(
                    scores[position]
                ),

                "chunk_id": chunk.get(
                    "chunk_id"
                ),

                "category": chunk.get(
                    "category"
                ),

                "report_type": chunk.get(
                    "report_type"
                ),

                "source_type": chunk.get(
                    "source_type"
                ),

                "content": chunk.get(
                    "content",
                    "",
                ),

                "metadata": chunk.get(
                    "metadata",
                    {},
                ),
            }

            results.append(
                result
            )

        return results