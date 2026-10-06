from __future__ import annotations

from typing import Iterable

import numpy as np
import torch
from FlagEmbedding import BGEM3FlagModel


class BGEM3Embedder:
    """
    PeerProof RAG용 BGE-M3 embedding wrapper.

    역할
    ----
    1. DART chunk embedding
    2. 사용자 query embedding

    현재는 BGE-M3의 dense embedding만 사용한다.
    sparse / ColBERT embedding은 이후 비교 실험에서 추가할 수 있다.
    """

    DEFAULT_MODEL_NAME = "BAAI/bge-m3"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        use_fp16: bool = True,
        max_length: int = 1024,
        batch_size: int = 4,
    ):
        self.model_name = model_name
        self.max_length = max_length
        self.batch_size = batch_size

        # --------------------------------------------------
        # Device 확인
        # --------------------------------------------------

        if torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"

        print(
            f"BGE-M3 device: {self.device}"
        )

        # CPU에서는 fp16을 사용하지 않는다.
        if self.device == "cpu":
            use_fp16 = False

        # --------------------------------------------------
        # 모델 로드
        # --------------------------------------------------

        self.model = BGEM3FlagModel(
            model_name,
            use_fp16=use_fp16,
            devices=self.device,
        )

    # ======================================================
    # 내부 embedding
    # ======================================================

    def _encode(
        self,
        texts: list[str],
    ) -> np.ndarray:
        """
        BGE-M3 dense embedding 생성.
        """

        if not texts:

            return np.empty(
                (0, 0),
                dtype=np.float32,
            )

        result = self.model.encode(
            texts,
            batch_size=self.batch_size,
            max_length=self.max_length,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )

        embeddings = np.asarray(
            result["dense_vecs"],
            dtype=np.float32,
        )

        # cosine similarity를 위해 L2 normalize
        norms = np.linalg.norm(
            embeddings,
            axis=1,
            keepdims=True,
        )

        norms = np.clip(
            norms,
            1e-12,
            None,
        )

        embeddings = (
            embeddings
            / norms
        )

        return embeddings

    # ======================================================
    # Document embedding
    # ======================================================

    def encode_documents(
        self,
        documents: Iterable[str],
    ) -> np.ndarray:

        documents = list(
            documents
        )

        return self._encode(
            documents
        )

    # ======================================================
    # Query embedding
    # ======================================================

    def encode_query(
        self,
        query: str,
    ) -> np.ndarray:

        query = query.strip()

        if not query:
            raise ValueError(
                "검색 질문이 비어 있습니다."
            )

        embedding = self._encode(
            [query]
        )

        return embedding[0]