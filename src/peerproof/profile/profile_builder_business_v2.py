"""
PeerProof Business Profile Builder v2

목적
----
기존 Profile 파이프라인을 수정하지 않고,
새 Business schema만 독립적으로 검증하기 위한 실험용 Builder입니다.

입력
----
- rag_chunks.json
- embeddings.npy
- Business v2 schema
- Gemini(OpenAI-compatible API)

출력
----
- business_profile_v2.json

중요 원칙
---------
1. Retrieval 실패를 곧바로 "미공시"로 판단하지 않습니다.
2. B5 Product Revenue Share는 LLM이 직접 계산하지 않습니다.
3. LLM은 검색된 공시 근거만 사용합니다.
4. 성공한 feature만 중간 저장합니다.
5. 429/503/연결 오류/타임아웃은 자동 재시도합니다.
6. API 실패 feature는 완료 처리하지 않습니다.
"""

from __future__ import annotations

import json
import os
import re
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from FlagEmbedding import BGEM3FlagModel
from openai import (
    OpenAI,
    InternalServerError,
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
)

from peerproof.profile.schema_business_v2 import BUSINESS_SCHEMA


DEFAULT_BGE_MODEL = "BAAI/bge-m3"

ALLOWED_STATUS = {
    "확인",
    "부분확인",
    "미공시",
    "해당없음",
    "검색불충분",
    "검토필요",
    "계산대기",
}


class BusinessProfileBuilderV2:
    def __init__(
        self,
        chunks_path: str | Path,
        embeddings_path: str | Path,
        output_path: str | Path,
        company_name: str,
        corp_code: str,
        analysis_as_of: str | None = None,
        query_top_k: int = 3,
        evidence_limit: int = 8,
        bge_model_name: str | None = None,
        resume: bool = True,
    ) -> None:
        load_dotenv()

        self.chunks_path = Path(chunks_path)
        self.embeddings_path = Path(embeddings_path)
        self.output_path = Path(output_path)

        self.company_name = company_name
        self.corp_code = corp_code
        self.analysis_as_of = analysis_as_of

        self.query_top_k = query_top_k
        self.evidence_limit = evidence_limit
        self.resume = resume

        self.bge_model_name = (
            bge_model_name
            or os.getenv("BGE_MODEL")
            or DEFAULT_BGE_MODEL
        )

        self.llm_api_key = os.getenv("LLM_API_KEY")
        self.llm_model = os.getenv("LLM_MODEL", "gemini-3.8-flash")
        self.llm_base_url = os.getenv(
            "LLM_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )

        if not self.llm_api_key:
            raise RuntimeError(
                "LLM_API_KEY가 없습니다. 프로젝트 루트의 .env를 확인하세요."
            )

        self._validate_input_files()

        self.chunks = self._load_chunks(self.chunks_path)
        self.embeddings = np.load(self.embeddings_path)

        if len(self.chunks) != len(self.embeddings):
            raise ValueError(
                "rag_chunks와 embeddings 개수가 다릅니다. "
                f"chunks={len(self.chunks)}, embeddings={len(self.embeddings)}"
            )

        self.embeddings = self._normalize_matrix(
            np.asarray(self.embeddings, dtype=np.float32)
        )

        self.embedder = BGEM3FlagModel(
            self.bge_model_name,
            use_fp16=True,
        )

        self.client = OpenAI(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
        )

    # ================================================================
    # 기본 입출력
    # ================================================================

    def _validate_input_files(self) -> None:
        if not self.chunks_path.exists():
            raise FileNotFoundError(
                f"rag_chunks.json을 찾을 수 없습니다: {self.chunks_path}"
            )

        if not self.embeddings_path.exists():
            raise FileNotFoundError(
                f"embeddings.npy를 찾을 수 없습니다: {self.embeddings_path}"
            )

    @staticmethod
    def _load_chunks(path: Path) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            chunks = data
        elif isinstance(data, dict):
            for key in ("chunks", "data", "items"):
                if isinstance(data.get(key), list):
                    chunks = data[key]
                    break
            else:
                raise ValueError(
                    "rag_chunks.json 형식을 해석할 수 없습니다. "
                    "list 또는 {'chunks': [...]} 형태여야 합니다."
                )
        else:
            raise ValueError("rag_chunks.json 최상위 형식이 올바르지 않습니다.")

        if not all(isinstance(x, dict) for x in chunks):
            raise ValueError("모든 chunk는 dict여야 합니다.")

        return chunks

    @staticmethod
    def _normalize_matrix(matrix: np.ndarray) -> np.ndarray:
        if matrix.ndim != 2:
            raise ValueError(
                f"embeddings.npy는 2차원이어야 합니다: shape={matrix.shape}"
            )

        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    @staticmethod
    def _normalize_vector(vector: np.ndarray) -> np.ndarray:
        vector = np.asarray(vector, dtype=np.float32).reshape(-1)
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm

    # ================================================================
    # Chunk 호환 처리
    # ================================================================

    @staticmethod
    def _metadata(chunk: dict[str, Any]) -> dict[str, Any]:
        meta = chunk.get("metadata")
        return meta if isinstance(meta, dict) else {}

    @classmethod
    def _chunk_text(cls, chunk: dict[str, Any]) -> str:
        meta = cls._metadata(chunk)

        candidates = (
            chunk.get("text"),
            chunk.get("content"),
            chunk.get("chunk_text"),
            chunk.get("page_content"),
            meta.get("text"),
            meta.get("content"),
        )

        for value in candidates:
            if isinstance(value, str) and value.strip():
                return value.strip()

        # table형 chunk가 dict/list로 보관된 경우 보조적으로 JSON 직렬화
        for key in ("table", "rows", "data"):
            value = chunk.get(key)
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)

        return ""

    @classmethod
    def _chunk_categories(cls, chunk: dict[str, Any]) -> set[str]:
        meta = cls._metadata(chunk)
        values: list[Any] = []

        for obj in (chunk, meta):
            for key in (
                "category",
                "categories",
                "profile_category",
                "retrieval_category",
            ):
                if key in obj:
                    values.append(obj[key])

        result: set[str] = set()

        for value in values:
            if isinstance(value, str):
                result.add(value.strip().lower())
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        result.add(item.strip().lower())

        return result

    @classmethod
    def _source_info(cls, chunk: dict[str, Any], index: int) -> dict[str, Any]:
        meta = cls._metadata(chunk)

        def pick(*keys: str) -> Any:
            for key in keys:
                if key in chunk and chunk[key] not in (None, ""):
                    return chunk[key]
                if key in meta and meta[key] not in (None, ""):
                    return meta[key]
            return None

        return {
            "chunk_index": index,
            "chunk_id": pick("chunk_id", "id", "index"),
            "category": pick("category", "profile_category"),
            "report": pick("report", "report_name", "report_type"),
            "rcept_no": pick("rcept_no", "receipt_no"),
            "filing_date": pick("filing_date", "rcept_dt", "date"),
            "period": pick("period", "period_end", "report_period"),
            "section": pick("section", "section_title", "heading"),
            "page": pick("page", "page_no"),
            "source_type": pick("source_type", "type"),
        }

    # ================================================================
    # Retrieval
    # ================================================================

    def _encode_query(self, query: str) -> np.ndarray:
        result = self.embedder.encode(
            [query],
            batch_size=1,
            max_length=2048,
        )

        if not isinstance(result, dict) or "dense_vecs" not in result:
            raise RuntimeError(
                "BGE-M3 encode 결과에서 dense_vecs를 찾지 못했습니다."
            )

        vector = np.asarray(result["dense_vecs"][0], dtype=np.float32)

        if vector.shape[0] != self.embeddings.shape[1]:
            raise ValueError(
                "Query embedding 차원과 저장된 embedding 차원이 다릅니다. "
                f"query={vector.shape[0]}, stored={self.embeddings.shape[1]}"
            )

        return self._normalize_vector(vector)

    def retrieve(
        self,
        queries: list[str],
        retrieval_categories: list[str],
    ) -> list[dict[str, Any]]:
        allowed = {x.lower() for x in retrieval_categories}

        # category metadata가 실제로 존재하는 chunk가 하나라도 있는지 확인
        has_any_category = any(
            bool(self._chunk_categories(chunk))
            for chunk in self.chunks
        )

        candidate_indices: list[int] = []

        for idx, chunk in enumerate(self.chunks):
            if not has_any_category:
                candidate_indices.append(idx)
                continue

            chunk_categories = self._chunk_categories(chunk)

            if chunk_categories & allowed:
                candidate_indices.append(idx)

        # metadata 불완전 때문에 후보가 0개가 되면
        # "미공시"로 처리하지 않고 전체 chunk에서 검색하도록 fallback
        category_filter_fallback = False
        if not candidate_indices:
            candidate_indices = list(range(len(self.chunks)))
            category_filter_fallback = True

        best_by_index: dict[int, dict[str, Any]] = {}

        for query in queries:
            qvec = self._encode_query(query)

            candidate_matrix = self.embeddings[candidate_indices]
            scores = candidate_matrix @ qvec

            order = np.argsort(scores)[::-1][: self.query_top_k]

            for local_pos in order:
                chunk_index = candidate_indices[int(local_pos)]
                score = float(scores[int(local_pos)])

                previous = best_by_index.get(chunk_index)
                if previous is not None and previous["score"] >= score:
                    continue

                chunk = self.chunks[chunk_index]
                best_by_index[chunk_index] = {
                    "score": score,
                    "matched_query": query,
                    "text": self._chunk_text(chunk),
                    "source": self._source_info(chunk, chunk_index),
                    "category_filter_fallback": category_filter_fallback,
                }

        ranked = sorted(
            best_by_index.values(),
            key=lambda x: x["score"],
            reverse=True,
        )

        # text가 비어 있는 chunk는 LLM 근거로 사용하지 않음
        ranked = [x for x in ranked if x["text"]]

        return ranked[: self.evidence_limit]

    # ================================================================
    # LLM
    # ================================================================

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        text = text.strip()

        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1 and start < end:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed

        raise ValueError("LLM 응답에서 JSON 객체를 추출하지 못했습니다.")

    @staticmethod
    def _evidence_for_prompt(evidence: list[dict[str, Any]]) -> str:
        blocks = []

        for i, item in enumerate(evidence, start=1):
            source = item["source"]
            header = (
                f"[E{i}] "
                f"score={item['score']:.4f} | "
                f"report={source.get('report')} | "
                f"date={source.get('filing_date')} | "
                f"period={source.get('period')} | "
                f"section={source.get('section')} | "
                f"page={source.get('page')}"
            )

            blocks.append(
                header
                + "\n"
                + item["text"][:5000]
            )

        return "\n\n".join(blocks)

    def _make_prompt(
        self,
        feature_key: str,
        feature: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> str:
        rules = "\n".join(
            f"- {rule}"
            for rule in feature.get("rules", [])
        )

        questions = "\n".join(
            f"- {query}"
            for query in feature.get("queries", [])
        )

        evidence_text = self._evidence_for_prompt(evidence)

        b5_extra = ""
        if feature_key == "product_revenue_share":
            b5_extra = """
[중요: B5 계산 규칙]
- 너는 매출비중을 직접 나누거나 합산해서 계산하면 안 된다.
- 공시에 비율이 직접 제시되어 있으면 그 값을 그대로 추출할 수 있다.
- 비율은 직접 없지만 numerator/denominator가 모두 확인되면 status를 "계산대기"로 두고
  calculation.required=true 로 반환한다.
- numerator와 denominator의 기간, 연결/별도, 통화, 단위, revenue scope가
  호환되는지 확인할 수 없으면 계산대기가 아니라 "부분확인" 또는 "검토필요"로 둔다.
"""

        return f"""
너는 PeerProof의 Business Profile 추출기다.

기업명: {self.company_name}
DART corp_code: {self.corp_code}
분석 기준일: {self.analysis_as_of or "미지정"}

분석 Feature:
- key: {feature_key}
- code: {feature.get("code")}
- label: {feature.get("label")}

다음 질문과 규칙을 기준으로 검색 근거만 분석하라.

[검색 질문]
{questions}

[판단 규칙]
{rules}

{b5_extra}

[검색된 공시 Evidence]
{evidence_text}

반드시 아래 원칙을 지켜라.

1. Evidence에 없는 사실을 일반지식으로 보완하지 않는다.
2. Retrieval 결과가 부족하다는 이유만으로 "미공시"라고 단정하지 않는다.
3. "미공시"는 충분한 범위를 검토했다는 근거가 있을 때만 사용한다.
4. 서로 충돌하는 Evidence가 해소되지 않으면 "검토필요"를 사용한다.
5. 최신 공시에서 단순히 언급되지 않았다는 이유만으로 과거의 직접 확인 사실을 삭제하지 않는다.
6. value는 비교기업 분석에 사용할 수 있도록 구체적으로 작성한다.
7. reason은 어떤 Evidence 때문에 그렇게 판단했는지 설명한다.
8. evidence_ids에는 실제 사용한 E번호만 넣는다.
9. B5에서 직접 공시되지 않은 비율을 네가 계산하지 않는다.

아래 JSON 형식만 출력하라.

{{
  "value": null,
  "status": "확인|부분확인|미공시|해당없음|검색불충분|검토필요|계산대기",
  "reason": "",
  "evidence_ids": ["E1"],
  "calculation": {{
    "required": false,
    "numerator": null,
    "denominator": null,
    "period": null,
    "scope": null,
    "currency": null,
    "unit": null
  }}
}}
""".strip()

    def _call_llm(
        self,
        prompt: str,
        max_retries: int = 4,
    ) -> dict[str, Any]:
        """
        Gemini/OpenAI-compatible API 호출.

        429, 5xx, 연결 오류, 타임아웃처럼 일시적일 수 있는 오류는
        지수형 대기(5 → 10 → 20 → 40초) 후 자동 재시도합니다.
        최종 실패 시 예외를 다시 올려 feature가 완료 처리되지 않게 합니다.
        """
        retry_delays = [5, 10, 20, 40]

        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.llm_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "공시 근거 기반 기업 프로필 추출기다. "
                                "추정하지 말고 JSON만 출력한다."
                            ),
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    temperature=0,
                )

                content = response.choices[0].message.content

                if not content:
                    raise RuntimeError(
                        "LLM 응답 content가 비어 있습니다."
                    )

                return self._extract_json(content)

            except (
                InternalServerError,
                RateLimitError,
                APIConnectionError,
                APITimeoutError,
            ) as exc:
                if attempt >= max_retries:
                    print()
                    print(
                        f"[LLM FAILED] {type(exc).__name__}: "
                        "최대 재시도 횟수를 초과했습니다."
                    )
                    raise

                wait_seconds = retry_delays[
                    min(attempt, len(retry_delays) - 1)
                ]

                print()
                print(
                    f"[LLM RETRY] {type(exc).__name__}: "
                    f"{wait_seconds}초 후 재시도 "
                    f"({attempt + 1}/{max_retries})"
                )

                time.sleep(wait_seconds)

    # ================================================================
    # 결과 정규화
    # ================================================================

    @staticmethod
    def _empty_result(
        feature: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        return {
            "code": feature.get("code"),
            "label": feature.get("label"),
            "value": None,
            "status": "검색불충분",
            "reason": reason,
            "evidence": [],
            "calculation": {
                "required": False,
                "numerator": None,
                "denominator": None,
                "period": None,
                "scope": None,
                "currency": None,
                "unit": None,
            },
        }

    def _normalize_llm_result(
        self,
        feature: dict[str, Any],
        llm_result: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        status = llm_result.get("status", "검토필요")
        if status not in ALLOWED_STATUS:
            status = "검토필요"

        ids = llm_result.get("evidence_ids", [])
        if not isinstance(ids, list):
            ids = []

        selected_evidence = []

        for evidence_id in ids:
            if not isinstance(evidence_id, str):
                continue

            match = re.fullmatch(r"E(\d+)", evidence_id.strip())
            if not match:
                continue

            pos = int(match.group(1)) - 1

            if 0 <= pos < len(evidence):
                item = deepcopy(evidence[pos])
                item["evidence_id"] = evidence_id
                selected_evidence.append(item)

        calculation = llm_result.get("calculation")
        if not isinstance(calculation, dict):
            calculation = {}

        calculation = {
            "required": bool(calculation.get("required", False)),
            "numerator": calculation.get("numerator"),
            "denominator": calculation.get("denominator"),
            "period": calculation.get("period"),
            "scope": calculation.get("scope"),
            "currency": calculation.get("currency"),
            "unit": calculation.get("unit"),
        }

        return {
            "code": feature.get("code"),
            "label": feature.get("label"),
            "value": llm_result.get("value"),
            "status": status,
            "reason": llm_result.get("reason", ""),
            "evidence": selected_evidence,
            "calculation": calculation,
        }

    # ================================================================
    # Output
    # ================================================================

    def _new_document(self) -> dict[str, Any]:
        return {
            "schema_version": "business_profile_v2",
            "company": {
                "company_name": self.company_name,
                "corp_code": self.corp_code,
                "analysis_as_of": self.analysis_as_of,
            },
            "retrieval": {
                "embedding_model": self.bge_model_name,
                "chunks_path": str(self.chunks_path),
                "embeddings_path": str(self.embeddings_path),
                "query_top_k": self.query_top_k,
                "evidence_limit": self.evidence_limit,
                "note": (
                    "현재 저장된 rag_chunks/embeddings를 사용하는 독립 Business v2 실험. "
                    "향후 full-document RAG로 교체 가능."
                ),
            },
            "llm": {
                "model": self.llm_model,
                "base_url": self.llm_base_url,
            },
            "business": {},
            "summary": {
                "completed_features": 0,
                "total_features": len(BUSINESS_SCHEMA),
            },
            "updated_at": None,
        }

    def _load_or_create_document(self) -> dict[str, Any]:
        if self.resume and self.output_path.exists():
            with self.output_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                raise ValueError("기존 output JSON 형식이 올바르지 않습니다.")

            data.setdefault("business", {})
            return data

        return self._new_document()

    def _save(self, document: dict[str, Any]) -> None:
        self.output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        document["summary"] = {
            "completed_features": len(document.get("business", {})),
            "total_features": len(BUSINESS_SCHEMA),
        }

        document["updated_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        temp_path = self.output_path.with_suffix(
            self.output_path.suffix + ".tmp"
        )

        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(
                document,
                f,
                ensure_ascii=False,
                indent=2,
            )

        temp_path.replace(self.output_path)

    # ================================================================
    # 실행
    # ================================================================

    def build_feature(
        self,
        feature_key: str,
    ) -> dict[str, Any]:
        if feature_key not in BUSINESS_SCHEMA:
            raise KeyError(
                f"알 수 없는 feature: {feature_key}"
            )

        feature = BUSINESS_SCHEMA[feature_key]

        evidence = self.retrieve(
            queries=feature.get("queries", []),
            retrieval_categories=feature.get(
                "retrieval_categories",
                ["business"],
            ),
        )

        if not evidence:
            return self._empty_result(
                feature,
                (
                    "현재 RAG 검색에서 사용할 수 있는 Evidence를 확보하지 못했습니다. "
                    "검색 실패를 미공시로 간주하지 않고 검색불충분으로 처리합니다."
                ),
            )

        prompt = self._make_prompt(
            feature_key=feature_key,
            feature=feature,
            evidence=evidence,
        )

        llm_result = self._call_llm(prompt)

        return self._normalize_llm_result(
            feature=feature,
            llm_result=llm_result,
            evidence=evidence,
        )

    def build(
        self,
        only_feature: str | None = None,
    ) -> dict[str, Any]:
        document = self._load_or_create_document()

        keys = (
            [only_feature]
            if only_feature
            else list(BUSINESS_SCHEMA.keys())
        )

        for feature_key in keys:
            if feature_key not in BUSINESS_SCHEMA:
                raise KeyError(
                    f"알 수 없는 feature: {feature_key}. "
                    f"가능한 값: {', '.join(BUSINESS_SCHEMA.keys())}"
                )

            if (
                self.resume
                and feature_key in document["business"]
            ):
                print(
                    f"[SKIP] {feature_key}: "
                    "기존 결과가 있어 건너뜁니다."
                )
                continue

            feature = BUSINESS_SCHEMA[feature_key]

            print()
            print(
                f"[{feature.get('code')}] "
                f"{feature_key} / {feature.get('label')}"
            )
            print("-" * 72)

            try:
                result = self.build_feature(feature_key)

            except Exception as exc:
                print()
                print(
                    f"[ERROR] {feature_key} 생성 실패"
                )
                print(
                    f"{type(exc).__name__}: {exc}"
                )
                print(
                    "실패한 feature는 Business Profile 결과에 "
                    "저장하지 않습니다."
                )
                print(
                    "다음 실행 시 다시 시도할 수 있습니다."
                )

                # 중요:
                # 실패한 feature를 document["business"]에 넣지 않습니다.
                # 따라서 completed_features에도 포함되지 않고,
                # resume=True여도 다음 실행에서 다시 시도됩니다.
                raise

            document["business"][feature_key] = result
            self._save(document)

            print(
                f"status={result['status']} | "
                f"evidence={len(result['evidence'])}"
            )
            print(
                f"중간 저장 완료: {self.output_path}"
            )

        return document
