"""PeerProof MVP: extract latest reported financial facts; no LTM or ratios.

Python 3.10+, standard library only. Input: existing OpenDART JSON wrappers.
Do not pass PDFs, LLM output, or the already aggregated finance_profile.json.
"""
from __future__ import annotations

import argparse
import calendar
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import zipfile


# key: (allowed statements, standard IDs, exact normalized name aliases)
ACCOUNT_RULES = {
    "revenue": (("IS", "CIS"), ("ifrs-full_Revenue",), ("매출액", "수익(매출액)", "매출", "영업수익")),
    "operating_income": (("IS", "CIS"), ("dart_OperatingIncomeLoss",), ("영업이익", "영업이익(손실)", "영업손익", "영업손실")),
    "net_income_parent": (("IS", "CIS"), ("ifrs-full_ProfitLossAttributableToOwnersOfParent",), ("지배기업 소유주지분", "지배기업의 소유주에게 귀속되는 당기순이익(손실)", "지배기업 소유주에게 귀속되는 순이익")),
    "total_assets": (("BS",), ("ifrs-full_Assets",), ("자산총계",)),
    "total_liabilities": (("BS",), ("ifrs-full_Liabilities",), ("부채총계",)),
    "total_equity": (("BS",), ("ifrs-full_Equity",), ("자본총계",)),
    "equity_parent": (("BS",), ("ifrs-full_EquityAttributableToOwnersOfParent",), ("지배기업 소유주지분", "지배기업의 소유주에게 귀속되는 자본", "지배기업 소유주에게 귀속되는 자본")),
    "operating_cash_flow": (("CF",), ("ifrs-full_CashFlowsFromUsedInOperatingActivities",), ("영업활동현금흐름", "영업활동으로 인한 현금흐름", "영업활동으로부터의 현금흐름")),
    "net_income_total": (("IS", "CIS"), ("ifrs-full_ProfitLoss",), ("당기순이익", "당기순이익(손실)", "분기순이익", "분기순이익(손실)", "반기순이익", "반기순이익(손실)", "당기순손실")),
    # Raw acquisition cash amounts only. CAPEX calculation is a later step.
    "ppe_purchase_cash": (("CF",), ("ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",), ("유형자산의 취득", "유형자산 취득", "유형자산의 증가")),
    "intangible_purchase_cash": (("CF",), ("ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities",), ("무형자산의 취득", "무형자산 취득", "무형자산의 증가")),
}
# Opening balances for ROE's average equity. Same BS row as the closing balance,
# read from frmtrm_amount (= prior fiscal year-end in FY, H1, Q1 and Q3 reports).
# Taking both ends from ONE report keeps restatements consistent.
BEGIN_BALANCES = {"equity_parent_begin": "equity_parent", "total_equity_begin": "total_equity"}
REPORTS = {"11011": (12, "FY"), "11013": (3, "Q1_YTD"),
           "11012": (6, "H1_YTD"), "11014": (9, "Q3_YTD")}


def normalize(text):
    return re.sub(r"\s+", "", str(text or ""))


def parse_amount(value):
    """Missing stays None; monetary integers never pass through float."""
    if value is None or normalize(value) in {"", "-", "—", "–"}:
        return None
    if isinstance(value, (float, bool)):
        raise ValueError("금액은 문자열 또는 정수로 전달하세요. float는 정밀도를 잃을 수 있습니다.")
    text = str(value).strip().replace(",", "").replace("−", "-")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("금액 형식 오류") from exc
    if not number.is_finite():
        raise ValueError("유한한 금액만 허용됩니다.")
    return int(number) if number == number.to_integral_value() else format(number, "f")


def parse_date(value):
    text = str(value).replace("-", "")
    return date(int(text[:4]), int(text[4:6]), int(text[6:8])).isoformat() if len(text) == 8 else date.fromisoformat(str(value)).isoformat()


def context_for(payload, as_of=None):
    rows = payload.get("statements", payload.get("list", []))
    if not rows:
        raise ValueError("재무 API 원본 계정이 없습니다.")
    if payload.get("status", "000") != "000":
        raise ValueError("재무 API 응답이 정상 상태가 아닙니다.")
    source = payload.get("source_report", {})
    def unique(key, wrapper=None):
        values = {str(r[key]) for r in rows if r.get(key)}
        if wrapper is not None:
            values.add(str(wrapper))
        if len(values) != 1:
            raise ValueError(f"{key}: 단일 기업/기간/접수번호를 확인할 수 없습니다.")
        return values.pop()
    corp = unique("corp_code", payload.get("corp_code"))
    year = int(unique("bsns_year", payload.get("business_year")))
    code = unique("reprt_code")
    receipt = unique("rcept_no", source.get("rcept_no"))
    if code not in REPORTS:
        raise ValueError("지원하지 않는 보고서 코드")
    scope = payload.get("fs_div")
    if scope not in {"CFS", "OFS"}:
        raise ValueError("원본 wrapper에 fs_div=CFS 또는 OFS를 지정해야 합니다.")
    if not re.fullmatch(r"\d{14}", receipt):
        raise ValueError("접수번호는 14자리 숫자여야 합니다.")
    receipt_date = parse_date(receipt[:8])
    filed = parse_date(source.get("rcept_date") or receipt_date)
    if filed != receipt_date:
        raise ValueError("메타데이터 접수일과 실제 접수번호 날짜가 일치하지 않습니다.")
    if as_of and filed > parse_date(as_of):
        raise ValueError("분석 기준일 이후 공시")
    months, kind = REPORTS[code]
    # Exact overrides permit other fiscal calendars; otherwise explicit MVP assumption.
    start, end = payload.get("period_start"), payload.get("period_end")
    if bool(start) != bool(end):
        raise ValueError("period_start와 period_end를 함께 입력해야 합니다.")
    if start:
        start, end = parse_date(start), parse_date(end)
        if start > end:
            raise ValueError("기간 시작일이 종료일보다 늦습니다.")
        origin = "provided_dates"
    else:
        try:
            fiscal_month = int(payload.get("fiscal_year_end_month", 12))
        except (TypeError, ValueError) as exc:
            raise ValueError("결산월은 1~12의 숫자여야 합니다.") from exc
        if not 1 <= fiscal_month <= 12:
            raise ValueError("결산월은 1~12의 숫자여야 합니다.")
        if fiscal_month != 12:
            raise ValueError("12월 외 결산기업은 period_start/period_end를 명시하세요.")
        start = date(year, 1, 1).isoformat()
        end = date(year, months, calendar.monthrange(year, months)[1]).isoformat()
        origin = "assumed_december_year_end"
    if end > filed:
        raise ValueError("재무기간 종료일이 공시일보다 늦습니다.")
    return {"corp_code": corp, "company": payload.get("company", corp),
            "report_name": source.get("report_name", kind), "rcept_no": receipt,
            "rcept_date": filed, "fs_div": scope, "report_code": code,
            "period_type": kind, "period_start": start, "period_end": end,
            "period_date_basis": origin, "analysis_as_of": parse_date(as_of) if as_of else None,
            "source_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + receipt}


def amount_field(row, context):
    # IS/CIS interim current amount is quarterly; cumulative field is mandatory.
    if row["sj_div"] in {"IS", "CIS"} and context["period_type"] != "FY":
        # Q1: 3-month amount == YTD, so an empty cumulative field may safely
        # fall back. H1/Q3 never fall back (3-month value would understate YTD).
        if context["period_type"] == "Q1_YTD":
            try:
                missing_ytd = parse_amount(row.get("thstrm_add_amount")) is None
            except ValueError:
                # A malformed cumulative number is invalid, not missing.
                missing_ytd = False
            if missing_ytd:
                return "thstrm_amount"
        return "thstrm_add_amount"
    # DART CF in the supplied files holds YTD in thstrm_amount; never apply
    # the IS-specific 3-month interpretation to all statements.
    return "thstrm_amount"


def extract_fact(rows, key, context, rule_key=None, field_override=None):
    statements, ids, aliases = ACCOUNT_RULES[rule_key or key]
    eligible = [r for r in rows if r.get("sj_div") in statements]
    matches = [r for r in eligible if r.get("account_id") in ids]
    method = "standard_id"
    if not matches:
        names = {normalize(x) for x in aliases}
        matches = [r for r in eligible if normalize(r.get("account_nm")) in names]
        method = "exact_name"
        # "지배기업 소유주지분" is also the name of the total-comprehensive-income
        # attribution row. Drop rows whose ID says Comprehensive. Do NOT use `ord`:
        # in APR's real Q3 file the comprehensive rows come before profit rows.
        # If both rows are untagged, the result stays "ambiguous" on purpose.
        matches = [r for r in matches if "Comprehensive" not in str(r.get("account_id"))]
    base = {"value": None, "status": "missing", "reason": "대응하는 원천 계정이 없습니다."}
    if not matches:
        return base
    candidates = []
    for row in matches:
        field = field_override or amount_field(row, context)
        raw = row.get(field)
        try:
            value = parse_amount(raw)
            status = "found" if value is not None else "missing"
            reason = None if value is not None else "필요한 기간 금액이 비어 있습니다."
        except ValueError as exc:
            value, status, reason = None, "invalid", str(exc)
        candidates.append({"value": value, "status": status, "reason": reason,
                           "currency": row.get("currency"), "unit_multiplier": 1,
                           "account_id": row.get("account_id"), "account_nm": row.get("account_nm"),
                           "statement_div": row.get("sj_div"), "statement_name": row.get("sj_nm"),
                           "account_detail": row.get("account_detail"), "amount_field": field,
                           "raw_amount": raw,
                           "period_label": row.get("frmtrm_nm") if field_override else row.get("thstrm_nm"),
                           "period_start": None if row["sj_div"] == "BS" else context["period_start"],
                           # Opening balance = day before the FY/YTD start.
                           "period_end": (date.fromisoformat(context["period_start"]) - timedelta(days=1)).isoformat()
                                         if field_override else context["period_end"],
                           "fs_div": context["fs_div"],
                           "rcept_no": context["rcept_no"], "source_url": context["source_url"],
                           "source_file": context.get("source_file"), "match_method": method,
                           "pdf_page": None})
    # Conflicting equal-priority candidates must not silently choose first.
    signatures = {(c["value"], c["currency"], c["status"]) for c in candidates}
    if len(signatures) > 1:
        return {"value": None, "status": "ambiguous", "reason": "동일 우선순위 계정에 서로 다른 값이 있습니다.", "candidates": candidates}
    return candidates[0]


def extract_report(payload, source_file="", as_of=None):
    context = context_for(payload, as_of)
    context["source_file"] = source_file
    rows = payload.get("statements", payload.get("list"))
    facts = {key: extract_fact(rows, key, context) for key in ACCOUNT_RULES}
    for key, closing in BEGIN_BALANCES.items():
        facts[key] = extract_fact(rows, key, context, rule_key=closing, field_override="frmtrm_amount")
    # OFS owns all its standalone NI/equity. Keep explicit provenance of fallback.
    if context["fs_div"] == "OFS":
        for parent, total in [("net_income_parent", "net_income_total"), ("equity_parent", "total_equity"),
                              ("equity_parent_begin", "total_equity_begin")]:
            if facts[parent]["status"] == "missing" and facts[total]["status"] == "found":
                facts[parent] = dict(facts[total], match_method="standalone_mapping", mapped_from=total)
    return {"context": context, "accounts": facts}


def select_latest(reports):
    """Most recent financial endpoint, then CFS at that endpoint, then filing date.

    Does not prefer old CFS over newer OFS or mix rows from different reports.
    """
    if not reports:
        raise ValueError("선택 가능한 보고서가 없습니다.")
    if len({r["context"]["corp_code"] for r in reports}) != 1:
        raise ValueError("서로 다른 기업을 한 프로필에 합칠 수 없습니다.")
    latest_end = max(r["context"]["period_end"] for r in reports)
    candidates = [r for r in reports if r["context"]["period_end"] == latest_end]
    consolidated = [r for r in candidates if r["context"]["fs_div"] == "CFS"]
    candidates = consolidated or candidates
    latest_date = max(r["context"]["rcept_date"] for r in candidates)
    candidates = [r for r in candidates if r["context"]["rcept_date"] == latest_date]
    if len(candidates) > 1:
        # Compare financial meaning, excluding only source-specific metadata.
        snapshots = {json.dumps({
            "period_start": r["context"]["period_start"],
            "period_end": r["context"]["period_end"],
            "period_type": r["context"]["period_type"],
            "fs_div": r["context"]["fs_div"],
            "accounts": {k: (a.get("value"), a.get("status"), a.get("currency"),
                               a.get("unit_multiplier"), a.get("period_start"), a.get("period_end"))
                         for k, a in r["accounts"].items()}},
            sort_keys=True, ensure_ascii=False) for r in candidates}
        if len(snapshots) > 1:
            raise ValueError("같은 기간·공시일의 보고서가 충돌합니다. 사용할 접수번호를 지정하세요.")
    # Compatible duplicates: stable representative choice, retaining all sources.
    # Receipt order is used only when the extracted facts are identical.
    candidates.sort(key=lambda r: (r["context"]["rcept_no"], r["context"].get("source_file", "")))
    selected = candidates[-1]
    duplicate_sources = [{k: r["context"].get(k) for k in ("rcept_no", "source_url", "source_file")}
                         for r in candidates] if len(candidates) > 1 else []
    return {"schema_version": "latest_report_v3", "measurement_basis": "reported_FY_or_YTD",
            "selection_policy": "latest_period_end_then_CFS_then_filing_date",
            "annualized": False, **selected, "compatible_duplicate_sources": duplicate_sources,
            "warnings": ["기업별 보고기간이 다를 수 있습니다. FY와 YTD를 같은 기간 실적으로 취급하지 마세요.",
                         "9~16번 계산 및 PER 평가는 이번 모듈에 포함되지 않습니다."]}


def read_payloads(path):
    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if "/finance/raw/" in name and name.endswith(".json"):
                    yield name, json.loads(archive.read(name))
    else:
        files = sorted(path.rglob("*.json")) if path.is_dir() else [path]
        for file in files:
            payload = json.loads(file.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and ("statements" in payload or "list" in payload):
                yield str(file), payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="finance/raw 폴더, API JSON, 또는 data.zip")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--as-of", required=True,
                        help="필수: 공통 정보 기준일(YYYY-MM-DD). 최초 신고 이전 분석이면 최초 접수일 전날")
    args = parser.parse_args()
    grouped, rejected = {}, []
    for name, payload in read_payloads(args.input):
        try:
            report = extract_report(payload, name, args.as_of)
            grouped.setdefault(report["context"]["corp_code"], []).append(report)
        except ValueError as exc:
            rejected.append({"source_file": name, "reason": str(exc)})
    if not grouped:
        parser.error("선택 가능한 재무 원본이 없습니다: " + json.dumps(rejected, ensure_ascii=False))
    output = {"companies": {corp: select_latest(reports) for corp, reports in grouped.items()},
              "rejected_reports": rejected}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"기업 {len(grouped)}개 추출 완료: {args.output}")


if __name__ == "__main__":
    main()
