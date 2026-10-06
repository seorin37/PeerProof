# PeerProof

기업 문서를 기반으로 유사 기업을 탐색하는 프로젝트입니다.

## Core Approach

- BGE-M3 embedding + cosine similarity
- Language network analysis
  - Keyword similarity
  - Edge similarity
  - Structural similarity
- Late Fusion
- Top 5 peer companies

## Environment

- Ubuntu WSL2
- Python 3.11
- VS Code

## DART 정기보고서 수집

`DART_API_KEY`를 프로젝트 루트의 `.env` 또는 환경변수에 설정합니다.
현재 수집 단계에는 `KRX_AUTH_KEY`가 필요하지 않습니다.

프로젝트 루트에서 실행:

```bash
python scripts/collect_dart_reports.py --company 에이피알 --start-date 20231005 --end-date 20261005
python scripts/collect_dart_reports.py --company 005930 --report-types annual
python -m unittest discover -s tests -p 'test_*.py'
```

기업명, 영문 정식명칭, 종목코드, DART 고유번호를 지원합니다.
동명이인이나 부분 일치가 여러 개이면 자동 선택하지 않고 오류를 반환합니다.
날짜를 생략하면 한국 시간 기준 실행일에서 최근 3년을 조회합니다.
조회 기간은 보고기간이 아닌 **공시 접수일** 기준입니다.

기본값은 사업·반기·분기보고서이며 최종보고서 조회(`last_reprt_at=Y`)를 사용합니다.
모든 정정 제출본이 필요하면 `--include-corrections`를 추가하세요.
이는 조회 시점에 이용 가능한 최종본이므로 과거 시점 분석에는 별도 공시 이력 관리가 필요합니다.

저장 구조:

```text
data/raw/dart/
  _cache/corp_codes.zip
  <corp_code>/
    manifest_<start_date>_<end_date>.json
    <rcept_no>/
      document.zip
      metadata.json
```

원문은 DART에서 받은 ZIP 그대로 보관합니다. XML 파일명 목록, 보고기간,
접수일, 공시뷰어 URL 및 다운로드 상태를 JSON에 기록합니다.
재실행할 때 정상 ZIP은 재사용하고 실패한 원문은 다시 다운로드합니다.
기업 목록을 갱신하려면 `--refresh-companies`를 사용합니다.
수집 결과가 없으면 빈 목록을 저장하며, 일부 원문 수집 실패 시 종료 코드는 1입니다.

비즈니스 모델 추출 모듈은 다음 단계에서 구현합니다. 현재 결과는 공시 원문과 메타데이터입니다.

공식 가이드:
- [공시검색](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001)
- [기업 고유번호](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018)
- [공시 원문](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003)
