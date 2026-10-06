# PeerProof Finance 구조 정리

## 1. Finance의 목적

PeerProof의 Finance 부분은 **IPO 대상기업과 후보기업의 재무 상태를 비교하고, 이후 PER 기반 가치평가에 활용하기 위한 모듈**이야.

Finance는 유사기업 자체를 선정하는 핵심 모델이라기보다는,

- 기업 규모
- 성장성
- 수익성
- 재무안정성
- 가치평가

를 보조적으로 비교하기 위해 사용해.

전체적으로는 아래 흐름으로 구성되어 있어.

```text
대상기업 + IPO 기준일
        ↓
IPO 기준일 이전 DART 공시 확인
        ↓
재무제표 API 자동 수집
        ↓
필요 재무계정 표준화
        ↓
기업별 Finance Profile 생성
        ↓
대상기업 ↔ 후보기업
최신 공통 재무기간 1:1 매칭
        ↓
재무지표 비교
        ↓
PER 등 가치평가
```

---

## 2. Finance 데이터 수집

Finance 데이터는 DART Open API에서 가져오도록 구현되어 있어.

관련 코드:

```text
src/peerproof/dart/finance.py
```

DART 재무제표 API를 사용해서 기업의 전체 재무 계정과목을 가져오는 역할이야.

현재는 **연결재무제표(CFS)를 우선 사용**하고,

```text
CFS가 있으면
→ CFS 사용

CFS가 없으면
→ OFS(별도재무제표) 사용
```

하도록 구현되어 있어.

---

## 3. IPO 기준일 이전 데이터만 사용

Finance에서도 Business Profile과 동일하게 **IPO 이후 데이터가 섞이지 않도록 하는 것**이 중요해.

예를 들어 대상기업 에이피알의 IPO 기준일이

```text
2023-12-22
```

라면,

```text
2023-12-22 이전에 공개된 재무정보만 사용
```

하는 방식이야.

이미 앞 단계에서 IPO 이전 보고서를 자동으로 선택해두기 때문에 Finance에서 사용자가 직접

```text
corp_code
사업연도
사업보고서 / 반기보고서 / 분기보고서
```

를 입력할 필요는 없어.

기존 DART metadata를 읽어서 자동으로 처리하도록 구현되어 있어.

관련 실행 코드:

```text
scripts/download_financial_statements.py
```

---

## 4. 현재 에이피알에서 자동 선택된 재무자료

에이피알의 경우 IPO 기준일 이전 자료 중 아래 자료가 선택됐어.

```text
2022 사업보고서
2023 반기보고서
2023 3분기보고서
```

Finance API에서는 각각 다음과 같이 변환해서 사용하고 있어.

```text
2022 사업보고서
→ 2022 annual
→ FY

2023 반기보고서
→ 2023 semiannual
→ H1_YTD

2023 3분기보고서
→ 2023 quarterly_3
→ Q3_YTD
```

현재 저장된 Finance 원본 데이터는 아래 위치에 있어.

```text
data/processed/에이피알/finance/raw/
```

예:

```text
2022_annual_CFS.json
2023_semiannual_CFS.json
2023_quarterly_3_CFS.json
```

---

## 5. 재무항목 표준화

DART Finance API에서는 기업별로 많은 계정과목이 내려오기 때문에, 필요한 항목만 표준화해서 추출하고 있어.

관련 코드:

```text
src/peerproof/finance/extractor.py
```

현재 추출하고 있는 핵심 계정은 다음과 같아.

| 표준 필드 | 의미 |
|---|---|
| `revenue` | 매출액 |
| `operating_income` | 영업이익 |
| `net_income` | 당기순이익 |
| `operating_cash_flow` | 영업활동현금흐름 |
| `total_assets` | 자산총계 |
| `total_liabilities` | 부채총계 |
| `total_equity` | 자본총계 |

기업마다 DART 계정명이 조금씩 다를 수 있기 때문에 단순히 `"매출액"`이라는 이름만 찾는 방식이 아니라,

```text
account_id
+
account_name
```

을 같이 이용해서 표준 계정으로 매핑하도록 구현하고 있어.

예를 들어 매출의 경우 기업에 따라

```text
매출액
매출
영업수익
수익(매출액)
```

등으로 다르게 표현될 수 있기 때문에 여러 후보명을 허용하는 방식이야.

---

## 6. 기간별 재무데이터 처리

Finance에서는 기간을 명확하게 구분해서 저장하고 있어.

현재 사용하고 있는 기간 형태는 다음과 같아.

```text
FY
→ 연간 실적

H1_YTD
→ 상반기 누적 실적

Q1_YTD
→ 1분기 누적 실적

Q3_YTD
→ 3분기 누적 실적
```

예를 들어 에이피알은 현재:

```text
2022_FY
2023_H1_YTD
2023_Q3_YTD
```

형태로 저장되어 있어.

반기나 분기 손익계산서의 경우 **해당 분기 단독 값이 아니라 누적값(YTD)** 을 사용하는 것이 중요해.

그래서 DART 데이터에서 가능하면:

```text
thstrm_add_amount
```

를 우선 사용하도록 구현되어 있어.

반면 자산 / 부채 / 자본과 같은 재무상태표 항목은 특정 시점의 값이기 때문에:

```text
thstrm_amount
```

를 사용해.

---

## 7. 현재 계산 중인 재무지표

현재 Finance 코드에서 계산하고 있는 지표는 다음과 같아.

### 영업이익률

```text
영업이익률
= 영업이익 / 매출액 × 100
```

### 순이익률

```text
순이익률
= 당기순이익 / 매출액 × 100
```

### 부채비율

```text
부채비율
= 부채총계 / 자본총계 × 100
```

### 부채자산비율

```text
부채자산비율
= 부채총계 / 자산총계 × 100
```

### 매출 성장률

```text
매출성장률
= (당기 매출 - 전기 동일기간 매출)
  / 전기 동일기간 매출
  × 100
```

---

## 8. 현재 생성되는 Finance Profile

Finance 원본 데이터를 표준화한 결과는 아래 위치에 저장돼.

```text
data/processed/기업명/finance/finance_profile.json
```

에이피알의 경우:

```text
data/processed/에이피알/finance/finance_profile.json
```

이 파일 안에는 기업이 현재 사용할 수 있는 재무기간과 각 기간별 재무지표가 저장되어 있어.

예:

```json
{
  "company": "에이피알",
  "available_periods": [
    "2022_FY",
    "2023_H1_YTD",
    "2023_Q3_YTD"
  ],
  "latest_period": "2023_Q3_YTD"
}
```

---

## 9. 대상기업과 후보기업의 재무기간 비교 방식

Finance에서 가장 중요한 기준 중 하나야.

모든 기업을 하나의 기간으로 강제로 맞추지 않고,

```text
대상기업 ↔ 후보기업
```

을 **1:1로 비교해서 둘 다 가지고 있는 가장 최신 공통 재무기간을 사용**하도록 구현했어.

관련 코드:

```text
src/peerproof/finance/matcher.py
```

예를 들어:

```text
에이피알
- 2022 FY
- 2023 H1
- 2023 Q3

후보기업 A
- 2022 FY
- 2023 H1
- 2023 Q3
```

이면:

```text
에이피알 vs A
→ 2023 Q3 기준
```

으로 비교해.

반면:

```text
후보기업 B
- 2022 FY
- 2023 H1
```

만 가지고 있다면:

```text
에이피알 vs B
→ 2023 H1 기준
```

으로 비교해.

또 후보기업 C가:

```text
2022 FY
```

만 가지고 있다면:

```text
에이피알 vs C
→ 2022 FY 기준
```

으로 비교하는 방식이야.

즉 특정 기업 때문에 모든 기업의 비교기간을 과거로 맞추는 방식이 아니라, **각 기업 pair별로 사용 가능한 최신 공통기간을 선택하는 방식**이야.

---

## 10. Finance Matcher 동작

현재 matcher는 아래처럼 동작해.

```text
Target Finance Profile
        +
Candidate Finance Profile
        ↓
두 기업의 사용 가능 기간 확인
        ↓
공통 기간 검색
        ↓
가장 최신 공통기간 선택
        ↓
동일 기간의 Finance 지표 반환
```

예를 들어:

```json
{
  "target_company": "에이피알",
  "candidate_company": "기업A",
  "finance_comparable": true,
  "comparison_period": "2023_Q3_YTD"
}
```

형태로 결과가 나오게 돼.

공통기간이 없다면:

```json
{
  "finance_comparable": false,
  "comparison_period": null,
  "reason": "공통 재무기간이 없습니다."
}
```

로 처리해.

---

## 11. Finance에서 아직 확정해야 하는 부분

현재는 기본적인 재무지표까지만 구현해둔 상태야.

Finance 담당에서 추가로 정했으면 하는 부분은 실제 IPO Peer 선정 및 가치평가에서 사용할 재무지표야.

예를 들면:

```text
매출성장률
영업이익률
순이익률
ROE
ROA
부채비율

PER
PBR
EV/EBITDA
```

등이 있는데,

여기서 실제로 어떤 지표가 필요한지 정하면 돼.

특히 아래 내용을 같이 정하면 좋을 것 같아.

```text
1. Peer 선정에 사용할 재무지표

2. 기업 규모 비교에 사용할 지표

3. 성장성 비교 지표

4. 수익성 비교 지표

5. 재무안정성 비교 지표

6. 최종 가치평가에 사용할 지표

7. 각 지표의 계산식
```

---

## 12. Finance 계산 Python 코드 작성 방식

Finance 계산 코드를 작성할 때는 특정 기업이나 특정 연도를 직접 코드에 넣지 않는 방식으로 작성하면 돼.

예를 들어:

```python
def calculate_per(
    market_cap,
    net_income,
):
    return market_cap / net_income
```

또는:

```python
def calculate_roe(
    net_income,
    equity,
):
    return net_income / equity * 100
```

처럼 **입력값을 받아 계산하는 함수 형태**로 작성하면 돼.

그러면 내가 나중에:

```text
finance_profile.json
        ↓
Finance 계산 함수
        ↓
후보기업 비교
        ↓
UI
```

구조로 바로 연결할 수 있어.

---

## 13. Finance 관련 주요 파일

### DART Finance API

```text
src/peerproof/dart/finance.py
```

역할:

```text
DART 재무제표 API 호출
```

---

### Finance 자동 다운로드

```text
scripts/download_financial_statements.py
```

역할:

```text
기존 DART metadata 확인
→ corp_code 자동 확인
→ IPO 이전 보고서 사용
→ 사업/반기/분기 재무제표 자동 다운로드
```

---

### Finance 계정 표준화

```text
src/peerproof/finance/extractor.py
```

역할:

```text
DART 재무계정
→ 핵심 계정 추출
→ 기간 표준화
→ 재무비율 계산
```

---

### Finance Profile 생성

```text
scripts/build_finance_profile.py
```

역할:

```text
Finance raw JSON
→ 표준화
→ finance_profile.json 생성
```

---

### 재무기간 Matcher

```text
src/peerproof/finance/matcher.py
```

역할:

```text
대상기업 Finance Profile
+
후보기업 Finance Profile
→ 최신 공통 재무기간 선택
```

---

### Matcher 테스트

```text
scripts/test_finance_matcher.py
```

역할:

```text
Q3 / H1 / FY / 공통기간 없음

각 상황에서 matcher가
정상적으로 동작하는지 테스트
```

---

## 14. 현재 Finance 진행상황

```text
DART Finance API 연결               ✅

IPO 이전 재무자료 자동 선택          ✅

사업/반기/분기 자동 판별             ✅

CFS 우선 / OFS fallback             ✅

재무 원본 JSON 저장                 ✅

핵심 재무계정 표준화                 ✅

FY / H1 / Q1 / Q3 기간 표준화       ✅

기본 재무비율 계산                   ✅

대상기업-후보기업
최신 공통기간 1:1 Matcher           ✅

추가 Finance 지표 선정               ⏳

PER / PBR / EV/EBITDA 등            ⏳

최종 가치평가 계산                   ⏳

UI 연결                             ⏳
```

---

## 15. Finance 담당 역할

### 내가 구현한 부분

```text
DART 재무 데이터 수집
IPO 기준일 이전 데이터 필터링
Finance 원본 저장
재무항목 표준화
재무기간 표준화
대상기업-후보기업 기간 Matching
전체 시스템 연결
```

### Finance 담당해서 봐줬으면 하는 부분

```text
IPO Peer 선정에 필요한 재무지표 선정

각 재무지표 계산식 확정

PER / PBR / EV/EBITDA 등
가치평가 지표 선정

최종 기업가치 계산 방식 정리

Finance 계산 Python 함수 작성
```

---

## 16. 최종 Finance 구조

최종적으로는 아래 구조로 연결할 예정이야.

```text
대상기업
        ↓
Finance Profile

후보기업 Top 5
        ↓
각 기업 Finance Profile

        ↓

대상기업 ↔ Top 1
대상기업 ↔ Top 2
대상기업 ↔ Top 3
대상기업 ↔ Top 4
대상기업 ↔ Top 5

        ↓

각 Pair별 최신 공통 재무기간 선택

        ↓

성장성 / 수익성 / 안정성 비교

        ↓

Peer 재무 비교

        ↓

PER 등 가치평가

        ↓

최종 UI에 표시
```

즉 Finance 담당에서는 **재무 데이터를 어떻게 가져오는지보다는, 가져온 데이터를 이용해서 어떤 재무지표를 계산하고 어떤 방식으로 가치평가할지를 중심으로 작업하면 돼.**
