import os

import requests
from dotenv import load_dotenv


load_dotenv()


class DartClient:
    """
    OpenDART API 공통 클라이언트.

    모든 DART API 요청은 이 클래스를 통해 수행한다.
    """

    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self):
        self.api_key = os.getenv("DART_API_KEY")

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

    def get(
        self,
        endpoint: str,
        params: dict | None = None,
        timeout: int = 60,
    ):
        """
        DART API GET 요청.
        """

        if params is None:
            params = {}

        params = dict(params)

        params["crtfc_key"] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"

        response = self.session.get(
            url,
            params=params,
            timeout=timeout,
        )

        response.raise_for_status()

        return response

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

        raise RuntimeError(
            "DART API 오류\n"
            f"status = {status}\n"
            f"message = {data.get('message')}"
        )