"""저장소/화면에서 사용할 최소 연결 예시. 추가 패키지 없이 실행 가능."""
from __future__ import annotations

from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
import json
from pathlib import Path
from peerproof.finance.finance_metrics import calculate_document, read_decimal

# 호출자 설정의 정밀도/반올림/trap을 계승하지 않습니다.
DISPLAY_CONTEXT = Context(prec=512, rounding=ROUND_HALF_UP)


def build_finance_payload(latest_document):
    """1~8 원천 계정을 유지하고, 9~16 계산 결과를 같은 기업에 붙인다."""
    calculated = calculate_document(latest_document)
    companies = {}
    for corp_code, latest_company in latest_document['companies'].items():
        metrics_company = calculated['companies'][corp_code]
        companies[corp_code] = {
            'context': latest_company['context'],
            'accounts': latest_company['accounts'],       # 1~8 + 숨김 원천 계정
            'metrics': metrics_company['metrics'],       # 9~16 (10번은 두 개)
            'warnings': metrics_company['warnings'],
        }
    return {'companies': companies, 'comparison_warnings': calculated['comparison_warnings']}


def format_amount(value, currency):
    """UI 금액 표시. KRW는 억원(100억 미만 소수 첫째 자리, 이상은 정수+쉼표). 원 단위 문자열/정수 입력.
    1~8번 원천 계정(accounts[*]['value'])과 9·13번 금액 지표에 같은 함수를 쓴다."""
    amount = read_decimal(value)
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isupper() or not currency.isalpha():
        raise ValueError("통화는 KRW/USD 같은 대문자 3자리 코드여야 합니다.")
    with localcontext(DISPLAY_CONTEXT):
        if currency != 'KRW':
            return f"{amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP):,} {currency}"
        eok = amount / Decimal(100_000_000)
        places = Decimal('0.1') if abs(eok) < 100 else Decimal('1')
        eok = eok.quantize(places, rounding=ROUND_HALF_UP)
        if eok == 0:
            eok = abs(eok)  # -0.0억 표시 방지
        return f"{eok:,}억 원"


def ui_text(metric):
    """0도 정상 값이다. value의 참/거짓으로 판단하지 않고 status를 확인한다."""
    if metric['status'] != 'computed':
        labels = {'missing': '자료 없음', 'review_required': '확인 필요', 'not_meaningful': '해석 불가'}
        return labels.get(metric['status'], '확인 필요')
    text = (format_amount(metric['value'], metric['currency']) if metric['unit'] == metric['currency']
            else f"{metric['display_value']}{metric['unit']}")
    # 0 처리 가정이 들어간 값은 표시를 구분한다(근거 보기에서 assumptions 노출).
    return text + (' *' if metric.get('assumptions') else '')


if __name__ == '__main__':
    folder = Path(__file__).resolve().parent
    source = json.loads((folder / 'APR_latest_report_input.json').read_text(encoding='utf-8'))
    result = build_finance_payload(source)
    company = result['companies']['01190568']
    names = {'revenue': '1 매출액', 'operating_income': '2 영업이익', 'net_income_parent': '3 지배주주 순이익',
             'total_assets': '4 자산총계', 'total_liabilities': '5 부채총계', 'total_equity': '6 자본총계',
             'equity_parent': '7 지배주주 자본', 'operating_cash_flow': '8 영업현금흐름'}
    for key, label in names.items():
        fact = company['accounts'][key]
        shown = format_amount(fact['value'], fact['currency']) if fact['status'] == 'found' else '자료 없음'
        print(f"{label}: {shown}")
    for metric in company['metrics'].values():
        print(f"{metric['ui_number']} {metric['name']}: {ui_text(metric)} ({metric['period_label']})")
