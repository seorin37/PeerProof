import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DART_API_KEY")
BASE_URL = "https://opendart.fss.or.kr/api"


def test_dart_connection():
    url = f"{BASE_URL}/company.json"

    params = {
        "crtfc_key": API_KEY,
        "corp_code": "00126380",  # 테스트용
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()

    print(data)


if __name__ == "__main__":
    test_dart_connection()