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


# ============================================================
# Profile LLM Client
# ============================================================

class ProfileLLMClient:

    def __init__(
        self,
        request_interval: float = 20.0,
        max_retries: int = 6,
    ):

        load_dotenv()

        api_key = os.getenv(
            "LLM_API_KEY"
        )

        model = os.getenv(
            "LLM_MODEL"
        )

        base_url = os.getenv(
            "LLM_BASE_URL"
        )

        if not api_key:
            raise ValueError(
                ".env에 LLM_API_KEY가 없습니다."
            )

        if not model:
            raise ValueError(
                ".env에 LLM_MODEL이 없습니다."
            )

        if not base_url:
            raise ValueError(
                ".env에 LLM_BASE_URL이 없습니다."
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

        self.model = model

        self.request_interval = (
            request_interval
        )

        self.max_retries = (
            max_retries
        )

        self._last_request_time = 0.0

    # ========================================================
    # Rate limit interval
    # ========================================================

    def _wait_for_interval(
        self,
    ) -> None:

        elapsed = (
            time.time()
            - self._last_request_time
        )

        wait_time = (
            self.request_interval
            - elapsed
        )

        if wait_time > 0:

            print(
                f"    LLM 요청 대기 "
                f"{wait_time:.1f}초..."
            )

            time.sleep(
                wait_time
            )

    # ========================================================
    # Retry seconds extraction
    # ========================================================

    @staticmethod
    def _extract_retry_seconds(
        error: Exception,
    ) -> float | None:

        text = str(error)

        # retry in 32s
        match = re.search(
            r"retry\s+in\s+([\d.]+)\s*s",
            text,
            re.IGNORECASE,
        )

        if match:

            return float(
                match.group(1)
            )

        # retry in 500ms
        match = re.search(
            r"retry\s+in\s+([\d.]+)\s*ms",
            text,
            re.IGNORECASE,
        )

        if match:

            return (
                float(
                    match.group(1)
                )
                / 1000.0
            )

        return None

    # ========================================================
    # Evidence formatting
    # ========================================================

    @staticmethod
    def _format_evidence(
        evidences: list[dict[str, Any]],
    ) -> str:

        blocks = []

        for evidence in evidences:

            evidence_id = (
                evidence[
                    "evidence_id"
                ]
            )

            chunk_id = (
                evidence.get(
                    "chunk_id"
                )
            )

            report = (
                evidence.get(
                    "report"
                )
                or evidence.get(
                    "source"
                )
                or "unknown"
            )

            section = (
                evidence.get(
                    "section"
                )
                or ""
            )

            content = (
                evidence.get(
                    "content"
                )
                or ""
            )

            block = (
                f"[{evidence_id}]\n"
                f"chunk_id: {chunk_id}\n"
                f"report: {report}\n"
                f"section: {section}\n"
                f"content:\n{content}"
            )

            blocks.append(
                block
            )

        return "\n\n".join(
            blocks
        )

    # ========================================================
    # Prompt
    # ========================================================

    def _build_prompt(
        self,
        category: str,
        field_name: str,
        field_config: dict[str, Any],
        evidences: list[dict[str, Any]],
    ) -> str:

        code = field_config.get(
            "code",
            field_name,
        )

        label = field_config.get(
            "label",
            field_name,
        )

        rules = field_config.get(
            "rules",
            [],
        )

        rules_text = "\n".join(
            f"- {rule}"
            for rule in rules
        )

        evidence_text = (
            self._format_evidence(
                evidences
            )
        )

        return f"""
너는 IPO 비교기업 분석을 위해 DART 공시만 분석하는 금융 문서 분석기다.

다음 Profile 항목을 DART 근거만 이용해서 작성하라.

[항목]
category: {category}
code: {code}
field: {field_name}
label: {label}

[판단 규칙]
{rules_text}

[절대 규칙]

1. 제공된 Evidence 이외의 외부지식을 사용하지 않는다.

2. 회사명, 경쟁사, 시장정보, 제품정보 등을
   네가 알고 있다는 이유로 추가하지 않는다.

3. Evidence에서 직접 확인되는 사실과
   분석을 위한 해석을 구분한다.

4. 숫자, 비율, 기업명, 국가명 등의 정보를
   Evidence에 없는데 만들어내면 안 된다.

5. 근거가 충분하면 status="확인"으로 한다.

6. 일부 정보만 확인되지만
   판단에 필요한 정보가 부족하면
   status="부분확인"으로 한다.

7. 관련 내용을 충분히 검색했지만
   해당 정보가 공시에 나타나지 않는 경우
   status="미공시"로 한다.

8. 해당 기업의 사업 구조상
   해당 항목 자체가 적용되지 않는 것이
   명확한 경우에만 status="해당없음"으로 한다.

9. 단순히 Evidence가 애매하다는 이유로
   "해당없음"을 사용하면 안 된다.

10. 근거가 부족하면 value를 억지로 생성하지 말고 null로 한다.

11. evidence_ids에는 반드시 아래 Evidence의
    ID만 사용한다.

12. Evidence 문장을 새로 만들거나
    존재하지 않는 Evidence ID를 만들지 않는다.

[Evidence]

{evidence_text}

[출력 형식]

반드시 아래 JSON 형식 하나만 반환하라.

{{
  "value": "최종 정리 내용 또는 null",
  "status": "확인 | 부분확인 | 미공시 | 해당없음",
  "company_claim": "회사가 직접 설명하거나 주장한 내용 또는 null",
  "interpretation": "Evidence를 기반으로 한 제한적인 해석 또는 null",
  "reason": "왜 이 status와 결과를 선택했는지 짧게 설명",
  "evidence_ids": ["E1", "E2"]
}}

추가 설명이나 Markdown은 출력하지 마라.
""".strip()

    # ========================================================
    # JSON parsing
    # ========================================================

    @staticmethod
    def _parse_json_response(
        text: str,
    ) -> dict[str, Any]:

        text = text.strip()

        # ```json 제거
        if text.startswith(
            "```"
        ):

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

            # 혹시 앞뒤 설명이 섞인 경우
            match = re.search(
                r"\{.*\}",
                text,
                re.DOTALL,
            )

            if not match:

                raise

            return json.loads(
                match.group(0)
            )

    # ========================================================
    # Validation
    # ========================================================

    @staticmethod
    def _validate_result(
        result: dict[str, Any],
        evidences: list[dict[str, Any]],
    ) -> dict[str, Any]:

        valid_statuses = {
            "확인",
            "부분확인",
            "미공시",
            "해당없음",
        }

        status = result.get(
            "status"
        )

        if status not in valid_statuses:

            raise ValueError(
                f"잘못된 status: {status}"
            )

        valid_ids = {
            evidence[
                "evidence_id"
            ]
            for evidence
            in evidences
        }

        evidence_ids = (
            result.get(
                "evidence_ids"
            )
            or []
        )

        evidence_ids = [
            evidence_id
            for evidence_id
            in evidence_ids
            if evidence_id
            in valid_ids
        ]

        result[
            "evidence_ids"
        ] = evidence_ids

        return result

    # ========================================================
    # Actual Gemini call
    # ========================================================

    def generate_profile_field(
        self,
        category: str,
        field_name: str,
        field_config: dict[str, Any],
        evidences: list[dict[str, Any]],
    ) -> dict[str, Any]:

        if not evidences:

            return {
                "value": None,
                "status": "미공시",
                "company_claim": None,
                "interpretation": None,
                "reason": (
                    "RAG 검색 결과에서 "
                    "관련 근거를 확보하지 못했습니다."
                ),
                "evidence_ids": [],
            }

        prompt = self._build_prompt(
            category=category,
            field_name=field_name,
            field_config=field_config,
            evidences=evidences,
        )

        last_error = None

        for attempt in range(
            1,
            self.max_retries + 1,
        ):

            try:

                self._wait_for_interval()

                print(
                    f"    Gemini 호출 "
                    f"({attempt}/{self.max_retries})"
                )

                response = (
                    self.client
                    .chat.completions.create(
                        model=self.model,

                        messages=[
                            {
                                "role": "user",
                                "content": prompt,
                            }
                        ],

                        # Gemini compatibility 때문에
                        # temperature는 넣지 않음
                    )
                )

                self._last_request_time = (
                    time.time()
                )

                content = (
                    response
                    .choices[0]
                    .message
                    .content
                )

                result = (
                    self._parse_json_response(
                        content
                    )
                )

                result = (
                    self._validate_result(
                        result,
                        evidences,
                    )
                )

                return result

            except (
                RateLimitError,
                InternalServerError,
                APIConnectionError,
                APITimeoutError,
            ) as error:

                last_error = error

                retry_seconds = (
                    self._extract_retry_seconds(
                        error
                    )
                )

                if retry_seconds is None:

                    retry_seconds = min(
                        20.0
                        * attempt,
                        120.0,
                    )

                retry_seconds += 2.0

                print(
                    f"    [RETRY] "
                    f"{type(error).__name__}"
                )

                print(
                    f"    {retry_seconds:.1f}초 후 재시도"
                )

                time.sleep(
                    retry_seconds
                )

            except Exception as error:

                last_error = error

                print(
                    f"    [ERROR] "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                break

        raise RuntimeError(
            "Gemini Profile 생성 실패"
        ) from last_error