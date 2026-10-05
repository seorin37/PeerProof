"""Minimal IPO profile contract: each observation carries its own provenance."""
from datetime import date
import re
from urllib.parse import urlparse

GROUPS = [
    {"id": "business_model", "title": "Business Model", "fields": [
        ["product_service", "Product / Service"],
        ["product_revenue_share", "Product Revenue Share"],
        ["revenue_model", "Revenue Model"],
        ["customer_type", "Customer Type"],
        ["distribution_channel", "Distribution Channel"],
    ]},
    {"id": "growth", "title": "Growth", "fields": [
        ["growth_revenue", "Revenue"],
        ["prior_year_revenue", "전년 동기 Revenue"],
        ["overseas_revenue", "해외매출"],
        ["overseas_revenue_share", "해외매출 비중"],
        ["growth_initiatives", "신규사업 / 신규제품 / 신규시장 / 신규채널 / 설비확장"],
    ]},
    {"id": "risk", "title": "Risk", "fields": [
        ["supplier_concentration", "Supplier / Raw Material Concentration"],
        ["customer_concentration", "Customer Concentration"],
        ["product_concentration", "Product Concentration"],
        ["geographic_concentration", "Geographic Concentration"],
        ["regulation", "Regulation"],
        ["competition", "Competition / Competitors / Differentiation"],
    ]},
    {"id": "financial_raw_data", "title": "Financial Raw Data", "fields": [
        ["financial_revenue", "Revenue"],
        ["operating_income", "Operating Income"],
        ["net_income", "Net Income"],
        ["total_assets", "Total Assets"],
        ["total_liabilities", "Total Liabilities"],
        ["equity", "Equity"],
    ]},
]
FIELDS = {key: label for group in GROUPS for key, label in group["fields"]}
OBSERVATION_FIELDS = {
    "value": "값", "evidence": "근거", "report_name": "보고서명",
    "received_date": "접수일", "section": "섹션", "link": "링크",
}


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: 반드시 입력해야 합니다.")
    if len(value) > 20000:
        raise ValueError(f"{label}: 20,000자 이하로 입력하세요.")
    return value.strip()


def valid_date(value, label):
    value = required_text(value, label)
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError(f"{label}: YYYY-MM-DD 날짜를 입력하세요.") from None


def valid_link(value, label):
    value = required_text(value, label)
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{label}: http 또는 https 보고서 링크를 입력하세요.")
    return value


def validate_profile(payload):
    if not isinstance(payload, dict):
        raise ValueError("프로필은 JSON 객체여야 합니다.")
    result = {"company_name": required_text(payload.get("company_name"), "기업명"),
              "analysis_as_of": valid_date(payload.get("analysis_as_of"), "분석 기준일")}
    items = payload.get("items")
    if not isinstance(items, dict):
        raise ValueError("항목별 값과 근거자료를 입력하세요.")
    if set(items) - set(FIELDS):
        raise ValueError("정의되지 않은 프로필 항목이 있습니다.")
    result["items"] = {}
    for group in GROUPS:
        for key, label in group["fields"]:
            prefix = f"{group['title']} / {label}"
            item = items.get(key)
            if not isinstance(item, dict):
                raise ValueError(f"{prefix}: 값과 근거자료를 입력하세요.")
            clean = {name: required_text(item.get(name), f"{prefix} · {caption}")
                     for name, caption in OBSERVATION_FIELDS.items()}
            clean["received_date"] = valid_date(clean["received_date"], f"{prefix} · 접수일")
            clean["link"] = valid_link(clean["link"], f"{prefix} · 링크")
            if clean["received_date"] > result["analysis_as_of"]:
                raise ValueError(f"{prefix}: 분석 기준일 이후 접수된 보고서는 사용할 수 없습니다.")
            result["items"][key] = clean
    return result
