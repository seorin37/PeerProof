import os
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv


load_dotenv()


class DartError(RuntimeError):
    """DART API 호출 실패.

    RuntimeError를 상속하므로 기존의 ``except RuntimeError`` 처리도 그대로 동작한다.
    메시지에는 요청 URL(인증키 포함)을 절대 넣지 않는다.
    """


class DartClient:
    """
    OpenDART API 공통 클라이언트.

    모든 DART API 요청은 이 클래스를 통해 수행한다.

    - ``get`` / ``get_json``: 기존 모듈(corp, disclosures, finance, downloader)이 사용.
    - ``json`` / ``archive``: 공시 수집(filings, collect_dart_reports)이 사용.
    """

    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("DART_API_KEY")

        if not self.api_key:
            raise ValueError(
                "DART_API_KEY가 설정되어 있지 않습니다.\n"
                ".env 파일에 DART_API_KEY를 입력하세요."
            )

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": "PeerProof/1.0"
            }
        )

    # ========================================================
    # Low-level request
    # ========================================================

    def _request(
        self,
        endpoint: str,
        params: dict | None = None,
        timeout: int = 60,
    ):
        """
        DART GET 요청. 실패 시 DartError.

        requests 예외 문자열에는 인증키가 들어 있는 URL이 포함될 수 있어
        예외 종류와 HTTP 상태 코드만 메시지에 남긴다.
        """

        params = dict(params or {})
        params["crtfc_key"] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.HTTPError as error:
            status_code = getattr(error.response, "status_code", "unknown")
            raise DartError(
                f"DART HTTP 오류 ({endpoint}): status_code={status_code}"
            ) from None
        except requests.RequestException as error:
            raise DartError(
                f"DART 요청 실패 ({endpoint}): {type(error).__name__}"
            ) from None

        return response

    # ========================================================
    # Legacy API (기존 모듈 호환)
    # ========================================================

    def get(
        self,
        endpoint: str,
        params: dict | None = None,
        timeout: int = 60,
    ):
        """
        DART API GET 요청.
        """

        return self._request(
            endpoint,
            params=params,
            timeout=timeout,
        )

    def get_json(
        self,
        endpoint: str,
        params: dict | None = None,
    ):
        """
        JSON 형태 DART API 호출.

        status:
        000 = 정상
        013 = 조회 결과 없음
        """

        response = self.get(
            endpoint=endpoint,
            params=params,
        )

        data = response.json()

        status = data.get("status")

        # 정상
        if status == "000":
            return data

        # 조회된 데이터 없음
        if status == "013":
            return {
                "status": "013",
                "message": data.get(
                    "message",
                    "조회된 데이터가 없습니다.",
                ),
                "list": [],
            }

        raise DartError(
            "DART API 오류\n"
            f"status = {status}\n"
            f"message = {data.get('message')}"
        )

    # ========================================================
    # Collection API
    # ========================================================

    def json(
        self,
        endpoint: str,
        **params,
    ):
        """
        JSON 엔드포인트 호출 (예: ``list.json``).

        000/013만 정상으로 반환하고 그 외 상태는 DartError.
        """

        return self.get_json(endpoint, params=params)

    def archive(
        self,
        endpoint: str,
        **params,
    ) -> bytes:
        """
        ZIP 바이너리 엔드포인트 호출 (예: ``document.xml``, ``corpCode.xml``).

        오류가 나면 DART는 ZIP 대신 ``<result><status>…</status>`` XML을 돌려주므로
        ZIP 시그니처가 아니면 상태 코드를 읽어 DartError로 올린다.
        """

        content = self._request(endpoint, params=params).content

        if content[:2] == b"PK":
            return content

        status = "unknown"
        message = ""

        try:
            root = ET.fromstring(content)
            status = (root.findtext("status") or "unknown").strip()
            message = (root.findtext("message") or "").strip()
        except ET.ParseError:
            pass

        raise DartError(
            f"DART error {status} ({endpoint})"
            + (f": {message}" if message else "")
        )
