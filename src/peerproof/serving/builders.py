"""
통합 프로필 / 유사도 결과 -> 프론트엔드가 받는 JSON (frontend/src/api/adapters.ts 형식)

프론트엔드 어댑터가 읽는 필드(snake_case)를 그대로 만든다. 점수는 0~1로 주고 프론트가 100을 곱한다.
회사 식별자(company_id)는 DART 고유번호(corp_code)를 쓴다.
"""

from __future__ import annotations

import re
from typing import Any

DART_VIEW_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="
QUOTE_LIMIT = 300
RATIO_KEYS = {"revenue_growth_rate", "overseas_revenue_ratio"}
NETWORK_METRICS = ("semantic_keyword_jaccard", "soft_weighted_edge_jaccard", "weighted_centrality_cosine")

SECTION_LABELS = {
    "business_model": "사업모델",
    "growth": "성장성(사업 확장)",
    "growth_metrics": "성장 지표",
    "risk": "리스크",
    "financial_raw": "재무 원천 데이터",
}
GROWTH_METRIC_LABELS = {
    "revenue": "매출(당기 누적)",
    "previous_period_revenue": "전년 동기 매출",
    "revenue_growth_rate": "매출 성장률(전년 동기 대비)",
    "overseas_revenue": "해외(수출) 매출",
    "overseas_revenue_ratio": "해외 매출 비중",
}


# ============================================================
# 값 -> 표시 문자열
# ============================================================

def flatten_value(value: Any, prefix: str = "") -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [f"{prefix}{text}"] if text else []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [f"{prefix}{value}"]
    if isinstance(value, list):
        leaves = [str(i).strip() for i in value if isinstance(i, (str, int, float)) and str(i).strip()]
        if leaves and len(leaves) == len(value):
            return [f"{prefix}{', '.join(leaves)}"]
        out: list[str] = []
        for item in value:
            out.extend(flatten_value(item, prefix))
        return out
    if isinstance(value, dict):
        out = []
        for key, item in value.items():
            out.extend(flatten_value(item, f"{prefix}{key}: "))
        return out
    return []


def format_krw(value: int | float) -> str:
    if abs(value) >= 100_000_000:
        return f"{value / 100_000_000:,.1f}억원"
    return f"{value:,.0f}원"


def display_value(value: Any) -> str | None:
    lines = flatten_value(value)
    return "\n".join(lines) if lines else None


def metric_value(key: str, value: Any) -> str | None:
    if value is None:
        return None
    if key in RATIO_KEYS:
        return f"{value * 100:.1f}%"
    return format_krw(value)


# ============================================================
# 근거
# ============================================================

def chunk_index(chunks: Any) -> dict[str, dict]:
    if isinstance(chunks, dict):
        chunks = chunks.get("chunks", [])
    return {c["chunk_id"]: c for c in (chunks or []) if isinstance(c, dict) and c.get("chunk_id")}


def make_evidence_ref(ref_id: str, item: dict, chunks: dict[str, dict]) -> dict:
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    chunk_id = item.get("chunk_id") or source.get("chunk_id")
    chunk = chunks.get(chunk_id, {}) if chunk_id else {}

    def pick(key: str) -> Any:
        return source.get(key) or item.get(key) or chunk.get(key)

    rcept_no = pick("rcept_no")
    section, page = pick("section"), pick("page")
    locator = " · ".join(p for p in (str(section) if section else "", f"p.{page}" if page else "") if p) or None
    text = item.get("text") or item.get("content") or chunk.get("content") or ""
    text = " ".join(str(text).split())
    return {
        "id": ref_id,
        "source": pick("report") or "출처 미상",
        "locator": locator,
        "url": f"{DART_VIEW_URL}{rcept_no}" if rcept_no else None,
        "published_at": pick("filing_date"),
        "quote": (text[:QUOTE_LIMIT] + ("…" if len(text) > QUOTE_LIMIT else "")) or None,
    }


def _section_items(section_key: str, section: dict, chunks: dict[str, dict], evidence: list[dict]) -> list[dict]:
    items = []
    for key, entry in (section or {}).items():
        if not isinstance(entry, dict) or not ("status" in entry or "value" in entry):
            continue
        ids = []
        for n, ev in enumerate(entry.get("evidence") or [], 1):
            if not isinstance(ev, dict):
                continue
            ref_id = f"{section_key}.{key}.{ev.get('evidence_id') or n}"
            evidence.append(make_evidence_ref(ref_id, ev, chunks))
            ids.append(ref_id)
        items.append({
            "key": key,
            "label": entry.get("label") or key,
            "value": display_value(entry.get("value")),
            "status": entry.get("status"),
            "evidence_ids": ids,
        })
    return items


# ============================================================
# 응답 만들기
# ============================================================

def company_id_of(unified: dict) -> str:
    return str((unified.get("company") or {}).get("corp_code") or "")


def build_company_summary(unified: dict) -> dict:
    company = unified.get("company") or {}
    return {"company_id": company_id_of(unified), "name": company.get("company_name"),
            "market": None, "sector": None, "industry": None}


def build_profile(unified: dict, chunks: Any = None) -> dict:
    index = chunk_index(chunks)
    company = unified.get("company") or {}
    reports = {r.get("rcept_no"): r.get("report_name") for r in (unified.get("source_reports") or {}).values()}
    evidence: list[dict] = []
    sections = []

    for key in ("business_model", "growth", "risk"):
        items = _section_items(key, unified.get(key) or {}, index, evidence)
        sections.append({"key": key, "label": SECTION_LABELS[key], "items": items})

    metric_items = []
    for key, label in GROWTH_METRIC_LABELS.items():
        metric = (unified.get("growth_metrics") or {}).get(key)
        if not isinstance(metric, dict):
            continue
        src = metric.get("source") or {}
        ref_id = f"growth_metrics.{key}"
        evidence.append({
            "id": ref_id,
            "source": reports.get(src.get("rcept_no")) or "출처 미상",
            "locator": src.get("section") or src.get("period"),
            "url": f"{DART_VIEW_URL}{src['rcept_no']}" if src.get("rcept_no") else None,
            "published_at": src.get("filing_date"),
            "quote": metric.get("note"),
        })
        metric_items.append({"key": key, "label": label, "value": metric_value(key, metric.get("value")),
                             "status": metric.get("status"), "evidence_ids": [ref_id]})
    sections.append({"key": "growth_metrics", "label": SECTION_LABELS["growth_metrics"], "items": metric_items})

    finance = unified.get("financial_raw") or {}
    context = finance.get("period_context") or {}
    fin_items = []
    fin_ref = None
    if context.get("rcept_no"):
        fin_ref = "financial_raw.source"
        evidence.append({
            "id": fin_ref,
            "source": context.get("report_name") or "재무제표",
            "locator": f"{context.get('period_start')} ~ {context.get('period_end')} ({context.get('fs_div')})",
            "url": f"{DART_VIEW_URL}{context['rcept_no']}",
            "published_at": context.get("rcept_date"),
            "quote": None,
        })
    for key, acc in (finance.get("accounts") or {}).items():
        fin_items.append({"key": key, "label": acc.get("label") or key,
                          "value": metric_value(key, acc.get("value")),
                          "status": acc.get("status"), "evidence_ids": [fin_ref] if fin_ref else []})
    sections.append({"key": "financial_raw", "label": SECTION_LABELS["financial_raw"], "items": fin_items})

    return {
        "company_id": company_id_of(unified),
        "company_name": company.get("company_name"),
        "industry": None,
        "period": f"{context.get('period_start')} ~ {context.get('period_end')}" if context else None,
        "basis": f"사업·반기·분기보고서 중 {unified.get('analysis_as_of')} 이전에 접수된 최신 공시",
        "version": unified.get("schema_version"),
        "generated_at": unified.get("built_at"),
        "summary": None,
        "sections": sections,
        "evidence": evidence,
    }


def _name_key(name: str) -> str:
    return re.sub(r"[\s\-_.,()㈜]|\(주\)|주식회사", "", str(name or "")).lower()


def network_score(row: dict, metrics: tuple[str, ...] = NETWORK_METRICS) -> float | None:
    values = [row[m] for m in metrics if isinstance(row.get(m), (int, float))]
    return sum(values) / len(values) if values else None


def build_similar(target_id: str, bge: dict | None, network: dict | None, fusion: dict) -> dict:
    """bge/network는 유사도 스크립트의 결과 JSON({"results": [...]})이다. fusion은 가중치 설정이다."""
    rows: dict[str, dict] = {}

    def row_for(item: dict) -> dict:
        key = str(item.get("corp_code") or _name_key(item.get("company_name")))
        row = rows.setdefault(key, {"company_id": str(item.get("corp_code") or key),
                                    "name": item.get("company_name"), "embedding_score": None, "network_score": None})
        return row

    for item in (bge or {}).get("results", []):
        row_for(item)["embedding_score"] = item.get("bge_similarity")
    for item in (network or {}).get("results", []):
        row_for(item)["network_score"] = network_score(item)

    w_e, w_n = float(fusion["embedding_weight"]), float(fusion["network_weight"])
    for row in rows.values():
        e, n = row["embedding_score"], row["network_score"]
        if e is not None and n is not None:
            row["fused_score"] = (w_e * e + w_n * n) / (w_e + w_n)
        else:
            row["fused_score"] = e if e is not None else n
    ranked = sorted((r for r in rows.values() if r["fused_score"] is not None), key=lambda r: -r["fused_score"])
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
    return {
        "target_id": target_id,
        "fusion": {"embedding_weight": w_e, "network_weight": w_n, "method": fusion.get("method")},
        "items": ranked,
    }


def build_network_stub(company_id: str) -> dict:
    return {"company_id": company_id, "nodes": [], "edges": []}


def build_valuation_stub(target_id: str, similar: dict, top_n: int | None = None) -> dict:
    """체크박스로 어떤 후보를 골라도 PER 표에 나오도록 기본은 후보 전체를 내려준다."""
    peers = [{"company_id": i["company_id"], "name": i["name"], "per": None, "included": True,
              "note": "PER 데이터 미연결"} for i in similar.get("items", [])[:top_n]]
    return {"target_id": target_id, "currency": "KRW", "basis": None, "peers": peers, "stats": None,
            "notes": ["PER 산출은 아직 연결되지 않았습니다."]}


# ============================================================
# 재무 지표 비교 (DART 공시만 사용, 시장가격 불필요)
# ============================================================

METRIC_DEFS = [
    {"key": "revenue_growth_rate", "label": "매출 성장률", "unit": "%", "note": "전년 동기 대비"},
    {"key": "overseas_revenue_ratio", "label": "해외 매출 비중", "unit": "%", "note": None},
    {"key": "operating_margin", "label": "영업이익률", "unit": "%", "note": "영업이익 ÷ 매출액"},
    {"key": "net_margin", "label": "순이익률", "unit": "%", "note": "전체 순이익 ÷ 매출액"},
    {"key": "debt_ratio", "label": "부채비율", "unit": "%", "note": "부채총계 ÷ 자본총계"},
]


def _ratio(numerator: Any, denominator: Any) -> float | None:
    if not isinstance(numerator, (int, float)) or not isinstance(denominator, (int, float)) or denominator == 0:
        return None
    return round(numerator / denominator, 4)


def company_metrics(unified: dict) -> dict:
    """한 회사의 지표 값(비율은 0.153 = 15.3%)과 기준 기간. 계산할 수 없으면 None."""
    growth = unified.get("growth_metrics") or {}
    accounts = (unified.get("financial_raw") or {}).get("accounts") or {}

    def val(group: dict, key: str):
        item = group.get(key)
        return item.get("value") if isinstance(item, dict) else None

    revenue = val(accounts, "revenue")
    context = (unified.get("financial_raw") or {}).get("period_context") or {}
    return {
        "values": {
            "revenue_growth_rate": val(growth, "revenue_growth_rate"),
            "overseas_revenue_ratio": val(growth, "overseas_revenue_ratio"),
            "operating_margin": _ratio(val(accounts, "operating_income"), revenue),
            "net_margin": _ratio(val(accounts, "net_income_total"), revenue),
            "debt_ratio": _ratio(val(accounts, "total_liabilities"), val(accounts, "total_equity")),
        },
        "period": f"{context.get('period_start')} ~ {context.get('period_end')}" if context.get("period_start") else None,
        "report": context.get("report_name"),
        "source_url": f"{DART_VIEW_URL}{context['rcept_no']}" if context.get("rcept_no") else None,
    }


def build_metrics(target_id: str, unified_by_id: dict[str, dict], similar: dict | None = None) -> dict:
    """대상기업 + 유사도 후보 전체의 지표 표. 체크박스 선택에 따른 통계는 화면에서 다시 계산한다."""
    order = [target_id] + [i["company_id"] for i in (similar or {}).get("items", [])]
    rows, seen = [], set()
    for company_id in order:
        if company_id in seen or company_id not in unified_by_id:
            continue
        seen.add(company_id)
        unified = unified_by_id[company_id]
        row = company_metrics(unified)
        row.update({"company_id": company_id, "name": (unified.get("company") or {}).get("company_name"),
                    "is_target": company_id == target_id})
        rows.append(row)
    return {
        "target_id": target_id,
        "basis": "DART 사업·반기·분기보고서 (기준일 이전 접수 최신 공시)",
        "metrics": METRIC_DEFS,
        "rows": rows,
        "notes": ["회사마다 기준 기간이 다를 수 있어 금액이 아닌 비율로만 비교합니다.",
                  "시장가격이 필요한 PER·공모가 범위는 DART 정기보고서만으로는 계산할 수 없어 제외했습니다."],
    }
