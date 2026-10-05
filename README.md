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

## Step 1 · IPO Business Profile

프로젝트 루트에서 실행합니다. 이 단계는 Python 표준 라이브러리만 사용합니다.
Python 3.11 이상이면 임베딩/GPU 패키지 설치 없이 실행할 수 있습니다.

```bash
python scripts/build_business_profile.py
```

브라우저에서 `http://127.0.0.1:8501`을 열고 기업명과 분석 기준일을 입력한 뒤,
다음 네 영역을 순서대로 작성합니다.

| 영역 | 최소 항목 |
| --- | --- |
| Business Model | Product / Service, Product Revenue Share, Revenue Model, Customer Type, Distribution Channel |
| Growth | Revenue, 전년 동기 Revenue, 해외매출, 해외매출 비중, 신규사업 / 신규제품 / 신규시장 / 신규채널 / 설비확장 |
| Risk | Supplier / Raw Material Concentration, Customer Concentration, Product Concentration, Geographic Concentration, Regulation, Competition / Competitors / Differentiation |
| Financial Raw Data | Revenue, Operating Income, Net Income, Total Assets, Total Liabilities, Equity |

신규사업 / 신규제품 / 신규시장 / 신규채널 / 설비확장은 하나의 항목으로 묶습니다.
총 22개 항목이며, 모든 항목에 다음 여섯 필드를 각각 기록해야 저장할 수 있습니다.

- `value`: 값. 금액과 비중은 기간, 단위, 연결/별도 기준을 함께 기록합니다.
- `evidence`: 원문 인용 또는 값을 뒷받침하는 근거 설명.
- `report_name`: 보고서명.
- `received_date`: 접수일 (YYYY-MM-DD).
- `section`: 보고서 섹션과 필요시 페이지.
- `link`: 보고서 원문으로 연결되는 http/https 링크.

공통 출처 목록만 저장하는 방식이 아니라 각 값에 근거를 직접 연결합니다.
Growth의 Revenue와 Financial Raw Data의 Revenue는 별도로 저장하므로
기간이나 회계 기준이 다른 값과 출처를 독립적으로 기록할 수 있습니다.

공란, 잘못된 날짜/링크, 분석 기준일 이후의 접수일은 서버에서도 검증합니다.
미공시 항목은 값에 “미공시”를 기록하고 확인한 보고서 구간을 근거로 적습니다.
출처가 기록됐다고 내용의 진실성이 자동 검증되는 것은 아닙니다.
원문 대조 전까지 `review.status`는 `unreviewed`로 유지됩니다.

저장 경로는 `data/processed/business_profiles/<id>.json`입니다.
서버를 재시작해도 파일이 유지되며, 저장된 기업을 선택해 수정할 수 있습니다.
JSON 내보내기는 마지막 저장본을 내려받습니다. 미저장 변경을 이동하거나
창을 닫을 때에는 브라우저에서 확인합니다.

```bash
python scripts/build_business_profile.py --port 8502 --data-dir /path/to/profiles
python -m unittest discover -s tests -v
```

### JSON 구조

`schema_version: 2`의 `manual_profile.items`에는 편집 가능한 원본 항목을,
`sections`에는 네 영역별 항목과 값·근거·보고서명·접수일·섹션·링크를 보관합니다.
기존 실험 코드가 읽는 `business_profile.profile_text`에는 Business Model의
값만 연결해 제공합니다. 재무 숫자는 사업 유사도 텍스트에 자동으로 섞지 않습니다.

이전 형식의 파일을 발견하면 원본을 덮어쓰지 않고 새 양식으로 작성하도록 안내합니다.
기존 `experiments/pilot_ipo` 코드는 수정하지 않습니다.
이 단계는 수동 입력·저장·수정까지 구현한 것이며 공시 자동 추출,
비교기업 추천 및 PER 계산은 아직 연결하지 않았습니다.
내 컴퓨터에서 한 사람이 사용하는 개발용 화면이며 외부 호스팅용 서버가 아닙니다.
