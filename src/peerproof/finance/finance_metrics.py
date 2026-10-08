"""PeerProof 9~16번: v3 최신 공시 출력으로 계산. Python 3.10+, 표준 라이브러리.

공식은 calculate_company() 아래쪽에 모았습니다.
금액은 Decimal로 계산하고, 입력이 부족하거나 서로 맞지 않으면 숫자를 만들지 않습니다.
LTM / 연환산 / PER / 원본 계정 추출은 이 모듈의 역할이 아닙니다.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, timedelta
from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext
import json
from pathlib import Path
import re

CALC_CONTEXT = Context(prec=512, rounding=ROUND_HALF_EVEN)
RATIO_CONTEXT = Context(prec=40, rounding=ROUND_HALF_EVEN)

REPORT_TYPES = {"11011": "FY", "11013": "Q1_YTD", "11012": "H1_YTD", "11014": "Q3_YTD"}
PERIOD_NAMES = {"FY": "연간", "Q1_YTD": "3개월 누적", "H1_YTD": "반기 누적", "Q3_YTD": "9개월 누적"}
FLOW_KEYS = {"revenue", "operating_income", "net_income_total", "net_income_parent",
             "operating_cash_flow", "ppe_purchase_cash", "intangible_purchase_cash"}
CASH_KEYS = {"operating_cash_flow", "ppe_purchase_cash", "intangible_purchase_cash"}
OPENING_KEYS = {"equity_parent_begin", "total_equity_begin"}
# 한 구성값만 missing일 때 원문 확인 근거가 있어야 0을 적용합니다.
# 단순 행 누락/계정 매핑 실패는 0이 아니며, 계산을 보류합니다.
CAPEX_COMPONENTS = ("ppe_purchase_cash", "intangible_purchase_cash")

# UI 번호 / 이름 / 입력 키 / 공식 / 결과 단위 (10번은 두 지표)
METRICS = {
    "cash_capex": (9, "현금 CAPEX", ("ppe_purchase_cash", "intangible_purchase_cash"),
                   "abs(ppe_purchase_cash) + abs(intangible_purchase_cash)", "currency"),
    "operating_margin": (10, "영업이익률", ("operating_income", "revenue"),
                         "operating_income / revenue * 100", "%"),
    "net_margin": (10, "전체 순이익률", ("net_income_total", "revenue"),
                   "net_income_total / revenue * 100", "%"),
    "roe": (11, "ROE", ("net_income_parent", "equity_parent_begin", "equity_parent"),
            "net_income_parent / ((equity_parent_begin + equity_parent) / 2) * 100", "%"),
    "debt_ratio": (12, "부채비율", ("total_liabilities", "total_equity"),
                   "total_liabilities / total_equity * 100", "%"),
    "simple_fcf": (13, "단순 FCF", ("operating_cash_flow", "ppe_purchase_cash", "intangible_purchase_cash"),
                   "operating_cash_flow - (abs(ppe_purchase_cash) + abs(intangible_purchase_cash))", "currency"),
    "cash_conversion": (14, "전체 현금전환율", ("operating_cash_flow", "net_income_total"),
                        "operating_cash_flow / net_income_total * 100", "%"),
    "cfo_margin": (15, "CFO 마진", ("operating_cash_flow", "revenue"),
                   "operating_cash_flow / revenue * 100", "%"),
    "capex_to_revenue": (16, "CAPEX/매출", ("ppe_purchase_cash", "intangible_purchase_cash", "revenue"),
                         "(abs(ppe_purchase_cash) + abs(intangible_purchase_cash)) / revenue * 100", "%"),
}


def read_decimal(value):
    """v3의 정수/십진 문자열만 허용. float, bool, NaN/Infinity는 계산 보류."""
    if not isinstance(value, (int, str, Decimal)) or isinstance(value, bool):
        raise ValueError("금액은 정수 또는 십진 문자열이어야 합니다(float 금지).")
    text = str(value).strip()
    if len(text) > 128 or not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
        raise ValueError("유효한 128자 이내 십진 금액이 아닙니다.")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("금액 형식 오류") from exc
    if not number.is_finite():
        raise ValueError("유한한 금액만 허용됩니다.")
    return number


def iso_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("날짜는 YYYY-MM-DD 문자열이어야 합니다.")
    return date.fromisoformat(value)


def context_errors(company):
    """공통 기준일/보고기간/연결 범위를 확인. 오류는 모든 지표에 전달."""
    errors = []
    if company.get("schema_version") != "latest_report_v3":
        errors.append("schema: latest_report_v3 출력만 입력하세요.")
    if company.get("annualized") is not False or company.get("measurement_basis") != "reported_FY_or_YTD":
        errors.append("basis: FY/YTD 원본이며 annualized=false여야 합니다.")
    ctx = company.get("context")
    if not isinstance(ctx, dict):
        return errors + ["context: 보고서 context가 없습니다."]
    if ctx.get("fs_div") not in {"CFS", "OFS"}:
        errors.append("scope: 연결/별도 범위가 확인되지 않습니다.")
    if not re.fullmatch(r"\d{8}", str(ctx.get("corp_code", ""))):
        errors.append("company: 8자리 corp_code가 필요합니다.")
    if REPORT_TYPES.get(ctx.get("report_code")) != ctx.get("period_type") or ctx.get("period_type") not in PERIOD_NAMES:
        errors.append("period_type: 보고서 코드와 기간 유형이 맞지 않습니다.")
    try:
        start, end = iso_date(ctx.get("period_start")), iso_date(ctx.get("period_end"))
        filed, as_of = iso_date(ctx.get("rcept_date")), iso_date(ctx.get("analysis_as_of"))
        if not start <= end <= filed <= as_of:
            errors.append("dates: 시작일 ≤ 종료일 ≤ 공시일 ≤ 기준일 조건 위반입니다.")
        receipt = str(ctx.get("rcept_no", ""))
        if not re.fullmatch(r"\d{14}", receipt) or receipt[:8] != filed.strftime("%Y%m%d"):
            errors.append("receipt: 접수번호와 공시일이 맞지 않습니다.")
        basis = ctx.get("period_date_basis")
        if basis == "assumed_december_year_end":
            month_day = {"FY": (12, 31), "Q1_YTD": (3, 31), "H1_YTD": (6, 30), "Q3_YTD": (9, 30)}
            if start != date(end.year, 1, 1) or (end.month, end.day) != month_day.get(ctx.get("period_type")):
                errors.append("calendar: 12월 결산 가정과 실제 기간이 맞지 않습니다.")
        elif basis != "provided_dates":
            errors.append("calendar: 기간 날짜의 근거가 확인되지 않습니다.")
    except (TypeError, ValueError):
        errors.append("dates: 기간/공시일/분석 기준일을 올바르게 입력하세요.")
    return errors


def period_label(ctx, metric_key):
    """비율을 연간 값으로 오해하지 않도록 실제 기간과 범위를 표시."""
    scope = {"CFS": "연결", "OFS": "별도"}.get(ctx.get("fs_div"), "범위 확인 필요")
    if metric_key == "debt_ratio":
        return f"{ctx.get('period_end')} 기말 · {scope}"
    name = PERIOD_NAMES.get(ctx.get("period_type"), "기간 확인 필요")
    if ctx.get("period_date_basis") == "provided_dates":
        name = "공시된 기간 누적"  # 비표준 회계기간에 9개월/12개월을 임의로 붙이지 않음
    return f"{ctx.get('period_start')}~{ctx.get('period_end')} · {name} · {scope}"


def checked_inputs(company, keys, common_errors):
    """기간·통화·단위·출처·계정 상태 검사. 사용 금액은 통화 기본 단위로 변환."""
    accounts = company.get("accounts", {})
    ctx = company.get("context", {})
    ctx = ctx if isinstance(ctx, dict) else {}
    problems, missing, values, currencies, multipliers = list(common_errors), [], {}, set(), set()
    if not isinstance(accounts, dict):
        return {}, None, "review_required", problems + ["accounts: 계정 객체가 없습니다."]
    for key in keys:
        fact = accounts.get(key)
        if not isinstance(fact, dict):
            missing.append(f"{key}: 원천 계정이 없습니다.")
            continue
        status = fact.get("status")
        if status == "missing":
            missing.append(f"{key}: {fact.get('reason') or '필요한 금액이 없습니다.'}")
            continue
        if status != "found":
            problems.append(f"{key}: 추출 상태 {status!r}, {fact.get('reason') or '확인 필요'}")
            continue
        try:
            value, multiplier = read_decimal(fact.get("value")), read_decimal(fact.get("unit_multiplier"))
            if multiplier <= 0 or multiplier != multiplier.to_integral_value() or multiplier > Decimal('1000000000000'):
                raise ValueError("단위 배수는 1~10^12 사이 양의 정수여야 합니다.")
            with localcontext(CALC_CONTEXT):
                values[key] = value * multiplier
            multipliers.add(multiplier)
        except ValueError as exc:
            problems.append(f"{key}: {exc}")
        currency = fact.get("currency")
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            problems.append(f"{key}: 통화가 확인되지 않습니다.")
        else:
            currencies.add(currency)
        if fact.get("fs_div") != ctx.get("fs_div"):
            problems.append(f"{key}: 연결/별도 범위가 보고서와 다릅니다.")
        if not ctx.get("rcept_no") or fact.get("rcept_no") != ctx.get("rcept_no"):
            problems.append(f"{key}: 선택 보고서와 접수번호가 다릅니다.")
        expected_divs = {"CF"} if key in CASH_KEYS else ({"IS", "CIS"} if key in FLOW_KEYS else {"BS"})
        if not isinstance(fact.get("statement_div"), str) or fact["statement_div"] not in expected_divs:
            problems.append(f"{key}: 재무제표 구분이 맞지 않습니다.")
        if key in OPENING_KEYS:
            try:
                expected_end = (iso_date(ctx.get("period_start")) - timedelta(days=1)).isoformat()
            except (ValueError, TypeError, OverflowError):
                expected_end = None
            expected_field = "frmtrm_amount"
        else:
            expected_end = ctx.get("period_end")
            expected_field = "thstrm_amount"
            if key in FLOW_KEYS - CASH_KEYS and ctx.get("period_type") != "FY":
                expected_field = "thstrm_add_amount"
                if ctx.get("period_type") == "Q1_YTD" and fact.get("amount_field") == "thstrm_amount":
                    expected_field = "thstrm_amount"
        expected_start = ctx.get("period_start") if key in FLOW_KEYS else None
        if fact.get("period_start") != expected_start or fact.get("period_end") != expected_end or expected_end is None:
            problems.append(f"{key}: 발생기간 또는 잔액 기준일이 맞지 않습니다.")
        if fact.get("amount_field") != expected_field:
            problems.append(f"{key}: 누적/기말/전기말 금액 필드가 맞지 않습니다.")
        # OFS에서만 전체 순이익/자본을 parent 입력으로 대응시킬 수 있음.
        if fact.get("match_method") == "standalone_mapping":
            mapping = {"net_income_parent": "net_income_total", "equity_parent": "total_equity",
                       "equity_parent_begin": "total_equity_begin"}
            if ctx.get("fs_div") != "OFS" or key not in mapping or fact.get("mapped_from") != mapping[key]:
                problems.append(f"{key}: 별도재무제표 parent 매핑이 맞지 않습니다.")
    if len(currencies) > 1:
        problems.append("currency: 사용하는 원천 계정의 통화가 다릅니다(환산하지 않음).")
    if len(multipliers) > 1:
        problems.append("unit: 사용하는 원천 계정의 단위 배수가 다릅니다(자동 혼합하지 않음).")
    # 해석 오류가 함께 있으면 missing보다 review_required를 우선한다.
    if problems:
        return {}, None, "review_required", problems + missing
    if missing:
        return {}, None, "missing", missing
    return values, next(iter(currencies)), "computed", []


def capex_zero_component(company):
    """(0 적용 키, 확인 오류). 원문 확인 근거가 없으면 missing을 그대로 둔다."""
    accounts = company.get("accounts")
    if not isinstance(accounts, dict):
        return None, []
    found = [k for k in CAPEX_COMPONENTS if isinstance(accounts.get(k), dict) and accounts[k].get("status") == "found"]
    missing = [k for k in CAPEX_COMPONENTS if isinstance(accounts.get(k), dict) and accounts[k].get("status") == "missing"]
    if len(found) != 1 or len(missing) != 1:
        return None, []  # 둘 다 누락, 키 없음, ambiguous/invalid는 대체하지 않음
    key = missing[0]
    confirmations = company.get("zero_cashflow_confirmations", {})
    if not isinstance(confirmations, dict):
        return None, ["zero_cashflow_confirmations는 계정별 확인 객체여야 합니다."]
    proof = confirmations.get(key)
    if proof is None:
        return None, []  # 확인 근거 없음: 기존 missing 처리
    if not isinstance(proof, dict):
        return None, [f"{key}: 무지출 확인 근거 형식 오류입니다."]
    if proof.get("verified") is False:
        return None, []  # 원문 확인 전에는 0 적용 금지
    ctx, fact, other = company.get("context", {}), accounts[key], accounts[found[0]]
    if not isinstance(ctx, dict):
        return None, [f"{key}: 보고서 context를 확인하세요."]
    errors = []
    if proof.get("verified") is not True or proof.get("conclusion") != "no_cash_outflow":
        errors.append(f"{key}: 원문 무지출 확인(verified=true, conclusion=no_cash_outflow)이 필요합니다.")
    for field in ("corp_code", "rcept_no", "fs_div", "period_start", "period_end"):
        if not isinstance(proof.get(field), str) or proof[field] != ctx.get(field):
            errors.append(f"{key}: 확인 근거의 {field}가 선택 보고서와 다릅니다.")
    if proof.get("currency") != other.get("currency") or not isinstance(proof.get("currency"), str):
        errors.append(f"{key}: 무지출 확인 통화가 다른 구성값과 다릅니다.")
    if not isinstance(proof.get("source_url"), str) or not proof["source_url"].strip() or proof["source_url"] != ctx.get("source_url") or proof["source_url"] != "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + str(ctx.get("rcept_no")):
        errors.append(f"{key}: 선택 공시의 source_url이 필요합니다.")
    for field in ("source_locator", "note"):
        if not isinstance(proof.get(field), str) or not proof[field].strip():
            errors.append(f"{key}: 원문 위치와 확인 내용({field})이 필요합니다.")
    # API가 비어 있는 행의 메타데이터를 보존했다면, 그 기간/출처도 무시하지 않음.
    for field in ("rcept_no", "fs_div", "period_start", "period_end", "currency"):
        if fact.get(field) is not None and fact[field] != proof.get(field):
            errors.append(f"{key}: 누락 행의 {field}와 무지출 확인 근거가 충돌합니다.")
    for field, expected in (("statement_div", "CF"), ("amount_field", "thstrm_amount")):
        if fact.get(field) is not None and fact[field] != expected:
            errors.append(f"{key}: 누락 행의 {field}가 취득 현금 계정 기준과 다릅니다.")
    if fact.get("unit_multiplier") is not None:
        try:
            if read_decimal(fact["unit_multiplier"]) != read_decimal(other.get("unit_multiplier")):
                errors.append(f"{key}: 누락 행과 다른 구성값의 단위 배수가 다릅니다.")
        except ValueError:
            errors.append(f"{key}: 누락 행의 단위 형식을 확인하세요.")
    for field in ("value", "raw_amount"):
        raw = fact.get(field)
        if raw is None or (isinstance(raw, str) and raw.strip() in {"", "-", "—", "–"}):
            continue
        try:
            if read_decimal(raw) != 0:
                errors.append(f"{key}: {field}의 비영(非零) 금액과 무지출 확인이 충돌합니다.")
        except ValueError:
            errors.append(f"{key}: {field} 형식 오류를 0으로 대체할 수 없습니다.")
    return (None, errors) if errors else (key, [])


def percentage(numerator, denominator):
    # 반복소수는 40 유효자리. 최종 표시용 반올림과 구분한다.
    with localcontext(CALC_CONTEXT):
        scaled_numerator = numerator * 100
    with localcontext(RATIO_CONTEXT):
        return scaled_numerator / denominator


def result_record(company, key, values, currency, status, reasons, value=None, assumptions=None, zero_confirmations=None):
    ui_number, name, inputs, formula, unit = METRICS[key]
    ctx = company.get("context", {})
    ctx = ctx if isinstance(ctx, dict) else {}
    accounts = company.get("accounts", {})
    accounts = accounts if isinstance(accounts, dict) else {}
    if key == "roe":
        name += " · " + ("공시된 기간" if ctx.get("period_date_basis") == "provided_dates"
                         else PERIOD_NAMES.get(ctx.get("period_type"), "기간 확인 필요"))
    display = None
    if value is not None:
        with localcontext(CALC_CONTEXT):
            display = format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
            if Decimal(display) == 0:
                display = "0.00"  # -0.00 표시 방지
    return {"ui_number": ui_number, "name": name, "value": format(value, "f") if value is not None else None,
            "display_value": display, "unit": currency if unit == "currency" else unit,
            "unit_multiplier": 1, "currency": currency, "status": status,
            "reason": "; ".join(reasons) if reasons else None, "reasons": reasons,
            "assumptions": list(assumptions or []),
            "zero_confirmations": deepcopy(zero_confirmations or {}),
            "formula": formula, "input_keys": list(inputs),
            "source_inputs": {k: deepcopy(accounts.get(k)) for k in inputs},
            "normalized_inputs": {k: format(v, "f") for k, v in values.items()},
            "period_type": ctx.get("period_type"), "period_start": None if key == "debt_ratio" else ctx.get("period_start"),
            "period_end": ctx.get("period_end"), "period_label": period_label(ctx, key),
            "fs_div": ctx.get("fs_div"), "analysis_as_of": ctx.get("analysis_as_of"), "annualized": False}


def calculate_company(company):
    """select_latest()의 기업 1개 출력 → 9개 계산 결과. 입력을 변경하지 않음."""
    if not isinstance(company, dict):
        raise ValueError("기업 입력은 v3 JSON 객체여야 합니다.")
    try:
        json.dumps(company, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("기업 입력은 NaN/Infinity 없는 JSON 호환 객체여야 합니다.") from exc
    ctx = company.get("context")
    if isinstance(ctx, dict):
        for field in ("corp_code", "fs_div", "report_code", "period_type", "period_date_basis",
                      "period_start", "period_end", "rcept_no", "rcept_date", "analysis_as_of"):
            if ctx.get(field) is not None and not isinstance(ctx[field], str):
                raise ValueError(f"context.{field}는 문자열이어야 합니다.")
    common_errors = context_errors(company)
    zero_key, zero_errors = capex_zero_component(company)
    metrics = {}
    for key, definition in METRICS.items():
        inputs = definition[2]
        skip = zero_key if zero_key in inputs else None
        values, currency, status, reasons = checked_inputs(
            company, tuple(k for k in inputs if k != skip),
            common_errors + (zero_errors if any(k in CAPEX_COMPONENTS for k in inputs) else []))
        value, assumptions, used_confirmations = None, [], {}
        if status == "computed" and skip:
            values[skip] = Decimal(0)
            proof = company["zero_cashflow_confirmations"][skip]
            assumptions = [f"{skip}: 원문 무지출 확인 후 0 적용. {proof['source_locator']} / {proof['note']}"]
            used_confirmations = {skip: proof}
        if status == "computed":
            # ----- 금융 공식: 각 지표는 필요한 계정만 사용 -----
            with localcontext(CALC_CONTEXT):
                if key in {"operating_margin", "net_margin", "cfo_margin", "capex_to_revenue"} and values["revenue"] <= 0:
                    status, reasons = "not_meaningful", ["매출액이 0 이하이므로 매출 대비 비율을 해석할 수 없습니다."]
                elif key == "cash_conversion" and values["net_income_total"] <= 0:
                    status, reasons = "not_meaningful", ["전체 순이익이 0 이하이므로 현금전환율을 해석할 수 없습니다."]
                elif key == "debt_ratio" and (values["total_equity"] <= 0 or values["total_liabilities"] < 0):
                    status, reasons = "not_meaningful", ["자본총계가 0 이하이거나 부채총계가 음수입니다."]
                elif key == "roe" and (values["equity_parent_begin"] <= 0 or values["equity_parent"] <= 0):
                    status, reasons = "not_meaningful", ["기초/기말 지배주주 자본이 0 이하이므로 ROE를 해석할 수 없습니다."]
                elif key == "roe" and company["context"]["period_date_basis"] == "provided_dates" and company["context"].get("opening_balance_date_verified") is not True:
                    status, reasons = "review_required", ["지정 회계기간의 전기말 자본이 기간 시작 직전 잔액인지 원문 확인이 필요합니다(opening_balance_date_verified=true)."]
                elif key == "cash_capex":
                    value = abs(values["ppe_purchase_cash"]) + abs(values["intangible_purchase_cash"])
                elif key == "operating_margin":
                    value = percentage(values["operating_income"], values["revenue"])
                elif key == "net_margin":
                    value = percentage(values["net_income_total"], values["revenue"])
                elif key == "roe":
                    average_equity = (values["equity_parent_begin"] + values["equity_parent"]) / 2
                    value = percentage(values["net_income_parent"], average_equity)
                elif key == "debt_ratio":
                    value = percentage(values["total_liabilities"], values["total_equity"])
                elif key == "simple_fcf":
                    capex = abs(values["ppe_purchase_cash"]) + abs(values["intangible_purchase_cash"])
                    value = values["operating_cash_flow"] - capex
                elif key == "cash_conversion":
                    value = percentage(values["operating_cash_flow"], values["net_income_total"])
                elif key == "cfo_margin":
                    value = percentage(values["operating_cash_flow"], values["revenue"])
                elif key == "capex_to_revenue":
                    capex = abs(values["ppe_purchase_cash"]) + abs(values["intangible_purchase_cash"])
                    value = percentage(capex, values["revenue"])
        metrics[key] = result_record(company, key, values, currency, status, reasons, value,
                                     assumptions if status == "computed" else [],
                                     used_confirmations if status == "computed" else {})
    warnings = ["기업별 FY/YTD 기간이 다를 수 있으므로 기간 라벨을 함께 표시하세요.",
                "현금 CAPEX는 유형·무형자산 취득 현금 합계이며, 단순 FCF는 가치평가용 FCFF/FCFE가 아닙니다."]
    ctx = company.get("context", {})
    if isinstance(ctx, dict) and ctx.get("period_date_basis") == "assumed_december_year_end":
        warnings.append("v3의 12월 결산·정상 회계연도 가정을 계승합니다. 다른 결산월은 실제 날짜를 전달하세요.")
    return {"schema_version": "finance_metrics_v3", "context": deepcopy(ctx),
            "measurement_basis": "reported_FY_or_YTD", "annualized": False,
            "metrics": metrics, "warnings": warnings}


def calculate_document(document):
    """v3 CLI의 companies 전체 출력 지원. 기업간 금액 합산/순위/PER는 하지 않음."""
    if not isinstance(document, dict) or not isinstance(document.get("companies"), dict) or not document["companies"]:
        raise ValueError("v3의 비어 있지 않은 companies 객체가 필요합니다.")
    try:
        json.dumps(document, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("입력은 NaN/Infinity 없는 JSON 호환 객체여야 합니다.") from exc
    companies = document["companies"]
    if any(not isinstance(v, dict) for v in companies.values()):
        raise ValueError("companies의 각 기업은 JSON 객체여야 합니다.")
    contexts = [v.get("context") for v in companies.values()]
    if any(not isinstance(c, dict) for c in contexts):
        raise ValueError("각 기업에 context 객체가 필요합니다.")
    if any(c.get("analysis_as_of") is not None and not isinstance(c["analysis_as_of"], str) for c in contexts):
        raise ValueError("analysis_as_of는 YYYY-MM-DD 문자열이어야 합니다.")
    dates = {c.get("analysis_as_of") for c in contexts}
    if len(dates) > 1:
        raise ValueError("대상기업과 비교기업의 analysis_as_of를 동일하게 전달하세요.")
    output = {}
    for corp_code, company in sorted(companies.items()):
        if str(corp_code) != str(company["context"].get("corp_code")):
            raise ValueError("companies의 키와 context.corp_code가 일치해야 합니다.")
        output[corp_code] = calculate_company(company)
    warnings = []
    contexts = [v.get("context", {}) for v in companies.values()]
    if len({(c.get("period_start"), c.get("period_end")) for c in contexts}) > 1:
        warnings.append("기업간 보고기간이 다릅니다. 금액·누적 ROE를 동일 기간 수치로 취급하지 마세요.")
    if len({c.get("fs_div") for c in contexts}) > 1:
        warnings.append("기업간 연결/별도 재무 범위가 다릅니다.")
    currencies = set()
    for company in companies.values():
        accounts = company.get("accounts", {})
        if isinstance(accounts, dict):
            for fact in accounts.values():
                if isinstance(fact, dict) and fact.get("status") == "found" and isinstance(fact.get("currency"), str):
                    currencies.add(fact["currency"])
    if len(currencies) > 1:
        warnings.append("기업간 통화가 다릅니다. 금액은 환산되지 않았습니다.")
    return {"schema_version": "finance_metrics_v3", "companies": output,
            "comparison_warnings": warnings, "rejected_reports": deepcopy(document.get("rejected_reports", []))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="finance_latest.py가 생성한 v3 출력 JSON")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("입력 원본을 보호하려면 출력은 다른 파일로 지정하세요.")
    try:
        document = json.loads(args.input.read_text(encoding="utf-8"))
        result = calculate_document(document)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"기업 {len(result['companies'])}개 계산 완료: {args.output}")


if __name__ == "__main__":
    main()
