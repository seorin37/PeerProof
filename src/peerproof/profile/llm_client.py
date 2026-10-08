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

        if not base_url:
            raise ValueError(
                ".env에 LLM_BASE_URL이 없습니다."
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

        self.model = model
        self.request_interval = request_interval
        self.max_retries = max_retries

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

        # 예:
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

        # 예:
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

            evidence_id = evidence[
                "evidence_id"
            ]

            chunk_id = evidence.get(
                "chunk_id"
            )

            report = (
                evidence.get("report")
                or evidence.get("source")
                or "unknown"
            )

            section = (
                evidence.get("section")
                or ""
            )

            content = (
                evidence.get("content")
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

        # ----------------------------------------------------
        # 팀원2 추가:
        # schema.py의 queries를 실제 LLM prompt에 전달
        # ----------------------------------------------------

        queries = (
            field_config.get("queries")
            or []
        )

        queries_text = "\n".join(
            f"- {query}"
            for query in queries
        ) or (
            "- 별도 질문 없음. "
            "항목과 판단 규칙에 따라 작성한다."
        )

        # ----------------------------------------------------
        # Rules
        # ----------------------------------------------------

        rules = field_config.get(
            "rules",
            [],
        )

        rules_text = "\n".join(
            f"- {rule}"
            for rule in rules
        )

        # ----------------------------------------------------
        # Evidence
        # ----------------------------------------------------

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

[Evidence에서 확인할 질문]
{queries_text}

질문은 확인할 대상을 지정하며, 질문에 포함된 전제는 사실이 아니다.
각 질문을 제공된 Evidence에서 확인하고, 확인된 내용을 항목에 맞게 종합하라.
질문에 대한 근거가 없으면 외부지식이나 추측으로 답을 채우지 마라.
확인하지 못한 사항은 reason에 명시하라.

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

5. 근거가 충분하면
   status="확인"으로 한다.

6. 일부 정보는 확인되지만
   판단에 필요한 정보가 부족하면
   status="부분확인"으로 한다.

7. 제공된 Evidence만으로 해당 항목을
   판단하기 어려운 경우
   status="검색불충분"으로 한다.

8. Evidence에서 관련 내용을 찾지 못했다는 사실만으로
   원문 전체에 해당 내용이 없다고 판단하지 않는다.

9. status="미공시"는
   해당 정보가 공시에 존재하지 않는다는 것을
   충분한 근거로 판단할 수 있는 경우에만 사용한다.

10. 해당 기업의 사업 구조상
    해당 항목 자체가 적용되지 않는 것이
    명확한 경우에만
    status="해당없음"으로 한다.

11. 단순히 Evidence가 애매하다는 이유로
    "해당없음"을 사용하면 안 된다.

12. 근거가 부족하면
    value를 억지로 생성하지 말고 null로 한다.

13. 회사의 주장·계획·기대효과와
    실제 확인된 사실을 구분한다.

14. value에는 Evidence에서 확인되는 사실을 우선 작성한다.

15. company_claim에는
    회사가 직접 설명한 계획, 주장, 기대효과 등을 작성한다.

16. interpretation에는
    Evidence를 바탕으로 허용되는 제한적인 해석만 작성한다.

17. Evidence가 뒷받침하지 않는 전망,
    성공 가능성, 예상 매출, 예상 수익성 등을 만들어내지 않는다.

18. 수치를 사용할 경우
    기간, 단위, 연결·별도 범위 등을 혼동하지 않는다.

19. evidence_ids에는 반드시 아래 Evidence의
    ID만 사용한다.

20. Evidence 문장을 새로 만들거나
    존재하지 않는 Evidence ID를 만들지 않는다.


[Evidence]

{evidence_text}


[출력 형식]

반드시 아래 JSON 형식 하나만 반환하라.

{{
  "value": "최종 정리 내용 또는 null",
  "status": "확인 | 부분확인 | 미공시 | 해당없음 | 검색불충분",
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

        # ```json ... ``` 제거
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

            # 앞뒤에 설명이 섞인 경우
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
            "검색불충분",
        }

        status = result.get(
            "status"
        )

        if status not in valid_statuses:

            raise ValueError(
                f"잘못된 status: {status}"
            )

        # ----------------------------------------------------
        # 실제로 존재하는 evidence_id만 허용
        # ----------------------------------------------------

        valid_ids = {
            evidence["evidence_id"]
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
            if evidence_id in valid_ids
        ]

        result[
            "evidence_ids"
        ] = evidence_ids

        # ----------------------------------------------------
        # 기본 필드 보정
        # ----------------------------------------------------

        result.setdefault(
            "value",
            None,
        )

        result.setdefault(
            "company_claim",
            None,
        )

        result.setdefault(
            "interpretation",
            None,
        )

        result.setdefault(
            "reason",
            "",
        )

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

        # ----------------------------------------------------
        # 중요:
        # RAG 검색 실패 != 공시 미공시
        #
        # Evidence가 하나도 없으면
        # LLM을 호출하지 않고 검색불충분 처리
        # ----------------------------------------------------

        if not evidences:

            return {
                "value": None,
                "status": "검색불충분",
                "company_claim": None,
                "interpretation": None,
                "reason": (
                    "RAG 검색 결과에서 관련 근거를 "
                    "확보하지 못했습니다. "
                    "검색 실패만으로 원문 전체에 "
                    "해당 정보가 미공시되었다고 "
                    "판단하지 않습니다."
                ),
                "evidence_ids": [],
            }

        # ----------------------------------------------------
        # Prompt 생성
        # ----------------------------------------------------

        prompt = self._build_prompt(
            category=category,
            field_name=field_name,
            field_config=field_config,
            evidences=evidences,
        )

        last_error = None

        # ----------------------------------------------------
        # Gemini 호출 + Retry
        # ----------------------------------------------------

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

                        # Gemini OpenAI compatibility 때문에
                        # temperature는 사용하지 않음
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

                if not content:

                    raise ValueError(
                        "LLM 응답 content가 비어 있습니다."
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

            # ------------------------------------------------
            # 일시적 API 오류
            # ------------------------------------------------

            except (
                RateLimitError,
                InternalServerError,
                APIConnectionError,
                APITimeoutError,
            ) as error:

                last_error = error

                # 실제 API가 retry 시간을 알려주면 우선 사용
                retry_seconds = (
                    self._extract_retry_seconds(
                        error
                    )
                )

                # 없으면 점진적으로 대기
                if retry_seconds is None:

                    retry_seconds = min(
                        20.0 * attempt,
                        120.0,
                    )

                # 약간의 여유 시간 추가
                retry_seconds += 2.0

                print(
                    f"    [RETRY] "
                    f"{type(error).__name__}"
                )

                print(
                    f"    {retry_seconds:.1f}초 후 재시도"
                )

                # 요청이 실패했더라도
                # 요청 시점 기준으로 interval 관리
                self._last_request_time = (
                    time.time()
                )

                # 마지막 시도라면
                # 불필요하게 sleep하지 않음
                if attempt >= self.max_retries:
                    break

                time.sleep(
                    retry_seconds
                )

            # ------------------------------------------------
            # Retry 대상이 아닌 오류
            # ------------------------------------------------

            except Exception as error:

                last_error = error

                print(
                    f"    [ERROR] "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                break

        # ----------------------------------------------------
        # API 호출 실패
        #
        # 여기서 "미공시" 등의 Profile 결과를 만들지 않는다.
        # 상위 builder가 실패로 인식할 수 있도록 예외 발생.
        # ----------------------------------------------------

        raise RuntimeError(
            "Gemini Profile 생성 실패"
        ) from last_error