from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from dotenv import load_dotenv

from openai import (
    OpenAI,
    RateLimitError,
    InternalServerError,
    APIConnectionError,
    APITimeoutError,
)


class ProfileLLMClient:
    """
    PeerProof Business Profile 생성용 LLM Client.

    기능
    ----
    - Gemini OpenAI-compatible API 사용
    - 요청 간격 제어
    - RateLimitError 자동 재시도
    - InternalServerError 자동 재시도
    - 연결/timeout 오류 자동 재시도
    - Gemini가 알려준 retry 시간 반영
    """

    def __init__(
        self,
        request_interval: float = 20.0,
        max_retries: int = 6,
    ):
        load_dotenv()

        api_key = os.getenv("LLM_API_KEY")
        model = os.getenv("LLM_MODEL")
        base_url = os.getenv("LLM_BASE_URL")

        if not api_key:
            raise ValueError(
                ".env에 LLM_API_KEY가 없습니다."
            )

        if not model:
            raise ValueError(
                ".env에 LLM_MODEL이 없습니다."
            )

        self.model = model
        self.request_interval = request_interval
        self.max_retries = max_retries

        self._last_request_time: float | None = None

        client_args = {
            "api_key": api_key,
        }

        if base_url:
            client_args["base_url"] = base_url

        self.client = OpenAI(
            **client_args
        )

        print(
            f"LLM model: {self.model}"
        )

        print(
            f"LLM request interval: "
            f"{self.request_interval:.0f}초"
        )

        print(
            f"LLM max retries: "
            f"{self.max_retries}"
        )

    # ======================================================
    # 요청 간격
    # ======================================================

    def _wait_for_interval(
        self,
    ) -> None:

        if self._last_request_time is None:
            return

        elapsed = (
            time.monotonic()
            - self._last_request_time
        )

        remaining = (
            self.request_interval
            - elapsed
        )

        if remaining > 0:

            print(
                f"API 호출 간격 조절: "
                f"{remaining:.1f}초 대기"
            )

            time.sleep(
                remaining
            )

    # ======================================================
    # Gemini retry 시간 읽기
    # ======================================================

    @staticmethod
    def _extract_retry_seconds(
        error_text: str,
    ) -> float | None:

        # 예:
        # Please retry in 31.999s
        match = re.search(
            r"retry in\s+([0-9.]+)\s*s",
            error_text,
            re.IGNORECASE,
        )

        if match:
            try:
                return float(
                    match.group(1)
                )
            except ValueError:
                pass

        # 예:
        # Please retry in 525.9ms
        match = re.search(
            r"retry in\s+([0-9.]+)\s*ms",
            error_text,
            re.IGNORECASE,
        )

        if match:
            try:
                milliseconds = float(
                    match.group(1)
                )

                return milliseconds / 1000.0

            except ValueError:
                pass

        return None

    # ======================================================
    # 재시도 대기시간 계산
    # ======================================================

    def _calculate_wait_time(
        self,
        error: Exception,
        attempt: int,
    ) -> float:

        error_text = str(
            error
        )

        retry_seconds = (
            self._extract_retry_seconds(
                error_text
            )
        )

        # Gemini가 기다릴 시간을 직접 알려준 경우
        if retry_seconds is not None:

            return max(
                retry_seconds + 3.0,
                self.request_interval,
            )

        # 서버 오류/연결 오류용 exponential backoff
        fallback = min(
            15.0 * attempt,
            90.0,
        )

        return max(
            fallback,
            self.request_interval,
        )

    # ======================================================
    # 실제 Gemini API 호출
    # ======================================================

    def _create_completion(
        self,
        messages: list[dict[str, str]],
    ):

        last_error: Exception | None = None

        for attempt in range(
            1,
            self.max_retries + 1,
        ):

            self._wait_for_interval()

            try:

                print(
                    f"Gemini 요청 "
                    f"({attempt}/{self.max_retries})"
                )

                self._last_request_time = (
                    time.monotonic()
                )

                response = (
                    self.client
                    .chat
                    .completions
                    .create(
                        model=self.model,
                        messages=messages,
                    )
                )

                return response

            # ==============================================
            # 429
            # ==============================================

            except RateLimitError as error:

                last_error = error

                if attempt == self.max_retries:
                    break

                wait_seconds = (
                    self._calculate_wait_time(
                        error=error,
                        attempt=attempt,
                    )
                )

                print()
                print(
                    "[RateLimitError]"
                )

                print(
                    "Gemini 호출 제한에 "
                    "걸렸습니다."
                )

                print(
                    f"{wait_seconds:.1f}초 후 "
                    "자동 재시도합니다."
                )

                print()

                time.sleep(
                    wait_seconds
                )

            # ==============================================
            # 500 / 502 / 503 / 504 계열
            # ==============================================

            except InternalServerError as error:

                last_error = error

                if attempt == self.max_retries:
                    break

                wait_seconds = (
                    self._calculate_wait_time(
                        error=error,
                        attempt=attempt,
                    )
                )

                print()
                print(
                    "[InternalServerError]"
                )

                print(
                    "Gemini 서버에 "
                    "일시적인 오류가 발생했습니다."
                )

                print(
                    f"{wait_seconds:.1f}초 후 "
                    "자동 재시도합니다."
                )

                print()

                time.sleep(
                    wait_seconds
                )

            # ==============================================
            # 네트워크 연결 문제
            # ==============================================

            except (
                APIConnectionError,
                APITimeoutError,
            ) as error:

                last_error = error

                if attempt == self.max_retries:
                    break

                wait_seconds = (
                    self._calculate_wait_time(
                        error=error,
                        attempt=attempt,
                    )
                )

                print()
                print(
                    "[API Connection Error]"
                )

                print(
                    f"{wait_seconds:.1f}초 후 "
                    "자동 재시도합니다."
                )

                print()

                time.sleep(
                    wait_seconds
                )

            # ==============================================
            # 예상하지 못한 오류
            # ==============================================

            except Exception:
                raise

        raise RuntimeError(
            "Gemini API 호출이 "
            f"{self.max_retries}회 모두 실패했습니다."
        ) from last_error

    # ======================================================
    # JSON 파싱
    # ======================================================

    @staticmethod
    def _extract_json(
        text: str,
    ) -> dict[str, Any]:

        text = text.strip()

        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

        try:

            return json.loads(
                text
            )

        except json.JSONDecodeError:

            start = text.find("{")
            end = text.rfind("}")

            if (
                start != -1
                and end != -1
                and end > start
            ):

                return json.loads(
                    text[
                        start:end + 1
                    ]
                )

            raise ValueError(
                "LLM 응답을 JSON으로 "
                "변환할 수 없습니다.\n"
                f"{text}"
            )

    # ======================================================
    # Profile 필드 생성
    # ======================================================

    def extract_field(
        self,
        company_name: str,
        field_name: str,
        question: str,
        evidence: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:

        if not evidence:

            return {
                "field": field_name,
                "value": None,
                "evidence_ids": [],
                "reason": (
                    "관련 DART 근거가 없습니다."
                ),
            }

        evidence_parts = []

        for item in evidence:

            evidence_parts.append(
                (
                    f"[EVIDENCE_ID: "
                    f"{item['chunk_id']}]\n"
                    f"보고서: "
                    f"{item['report_type']}\n"
                    f"자료유형: "
                    f"{item['source_type']}\n"
                    f"검색점수: "
                    f"{item['score']:.4f}\n"
                    f"{item['content']}"
                )
            )

        evidence_context = (
            "\n\n".join(
                evidence_parts
            )
        )

        system_prompt = """
당신은 기업공시 분석 전문가입니다.

반드시 제공된 DART 공시 근거만 이용하십시오.

규칙:
1. 제공되지 않은 사실은 추측하지 마십시오.
2. 외부 지식을 사용하지 마십시오.
3. 근거가 부족하면 value는 null로 반환하십시오.
4. evidence_ids는 제공된 EVIDENCE_ID 중에서만 선택하십시오.
5. 수치나 사실을 임의로 생성하지 마십시오.
6. 서로 다른 시점의 내용이 충돌하면 더 최근 공시를 우선하십시오.
7. 단, 근거가 부족하면 단정하지 마십시오.
8. 결과는 반드시 JSON 객체 하나만 반환하십시오.
9. Markdown 코드 블록은 사용하지 마십시오.
"""

        user_prompt = f"""
기업명:
{company_name}

추출 필드:
{field_name}

질문:
{question}

아래는 BGE-M3 RAG가 검색한 DART 근거입니다.

==============================
DART EVIDENCE
==============================

{evidence_context}

==============================

반드시 위 근거에 있는 정보만 사용하십시오.

아래 JSON 구조로 반환하십시오.

{{
  "field": "{field_name}",
  "value": "근거 기반 핵심 내용 또는 null",
  "evidence_ids": [
    "실제로 사용한 evidence id"
  ],
  "reason": "이 값을 선택한 근거를 간단히 설명"
}}
"""

        response = (
            self._create_completion(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ]
            )
        )

        content = (
            response
            .choices[0]
            .message
            .content
        )

        if not content:

            raise ValueError(
                "Gemini 응답이 비어 있습니다."
            )

        result = (
            self._extract_json(
                content
            )
        )

        # ==================================================
        # Gemini가 존재하지 않는 evidence ID를
        # 만들어냈을 경우 제거
        # ==================================================

        valid_ids = {
            item["chunk_id"]
            for item in evidence
        }

        returned_ids = (
            result.get(
                "evidence_ids",
                [],
            )
            or []
        )

        result[
            "evidence_ids"
        ] = [
            evidence_id
            for evidence_id
            in returned_ids
            if evidence_id in valid_ids
        ]

        return result