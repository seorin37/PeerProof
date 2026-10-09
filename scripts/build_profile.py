#!/usr/bin/env python
"""
PeerProof 공통 프로필 생성 파이프라인 (대상기업 / 후보기업 공용)

회사 하나를 인자만으로 처리한다. 기존 단계별 스크립트(input() 방식)를 수정하지 않고
순서대로 실행하면서 질문에 자동으로 답을 넣고, 마지막에 하나의 통합 프로필 JSON을 만든다.

기준일 규칙
-----------
--as-of(YYYYMMDD)가 분석 기준일(cutoff)이다. 그날 이후에 접수된 공시는 쓰지 않는다.
  - 실제 사용: 분석하는 날짜를 준다(증권신고서가 아직 없는 기업).
  - 과거 시점 재현(백테스트): 예를 들어 에이피알은 신고서 제출 전날인 20231221을 준다.
--ipo-date(YYYYMMDD)는 이전 이름으로 계속 받는다. 분석 기준일은 그 전날이다.
(--as-of 20231221 과 --ipo-date 20231222 는 같은 실행이다.)
대상기업과 후보기업은 같은 분석 기준일로 실행해야 한다. 둘 중 하나는 반드시 줘야 한다.

사용 예 (프로젝트 루트에서)
---------------------------
    python scripts/build_profile.py --company 에이피알 --stock-code 278470 --as-of 20231221
    python scripts/build_profile.py --company 에이피알 --stock-code 278470 --as-of 20231221 --dry-run
    python scripts/build_profile.py --company 에이피알 --stock-code 278470 --as-of 20231221 --assemble-only

단계
----
 1 download      DART 정기보고서(사업/반기/분기) 중 cutoff 이전 최신 각 1건 수집
 2 preprocess    원문 전처리 (document.md / tables.json)
 3 evidence      profile_evidence.json 생성
 4 chunks        rag_chunks.json 생성
 5 embeddings    embeddings.npy 생성 (test_profile_rag.py 안에 있는 임베딩 단계)
 6 enrich        Business 근거 메타데이터(접수번호/공시일/기간 등) 보강
 7 business_v2   Business Profile v2 (LLM)
 8 growth        Growth 항목 (LLM)
 9 risk          Risk 항목 (LLM)
10 fin_download  재무제표 API 수집
11 fin_profile   finance_profile.json
12 fin_latest    최신 공통 재무기간 추출 (--as-of 적용)
13 fin_metrics   재무지표 계산
14 assemble      통합 프로필 + 완성도 + 기준일 누수 점검
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]

STEP_KEYS = [
    "download",
    "preprocess",
    "evidence",
    "chunks",
    "embeddings",
    "enrich",
    "business_v2",
    "growth",
    "risk",
    "fin_download",
    "fin_profile",
    "fin_latest",
    "fin_metrics",
    "assemble",
]

REPORT_TYPES = ("annual", "semiannual", "quarterly")

UNIFIED_FILENAME = "profile_unified.json"
UNIFIED_SCHEMA = "peerproof_profile_unified_v1"


# ============================================================
# 날짜 / 경로
# ============================================================


def compute_cutoff(ipo_date: str) -> str:
    """IPO 기준일(YYYYMMDD) -> 분석 기준일(YYYY-MM-DD, 전날)."""
    try:
        base = datetime.strptime(ipo_date, "%Y%m%d")
    except ValueError as error:
        raise ValueError(
            f"--ipo-date는 YYYYMMDD 형식이어야 합니다: {ipo_date}"
        ) from error
    return (base - timedelta(days=1)).strftime("%Y-%m-%d")


def compact(date_text: str) -> str:
    return date_text.replace("-", "")


class Paths:
    def __init__(self, root: Path, company: str):
        self.root = root
        self.company = company
        self.raw = root / "data" / "raw" / "dart" / company
        self.processed = root / "data" / "processed" / company
        self.profile = self.processed / "profile"
        self.rag = self.processed / "rag"
        self.finance = self.processed / "finance"
        self.state = root / "data" / "processed" / ".build_state" / f"{company}.json"

    @property
    def raw_metadata(self) -> Path:
        return self.raw / "metadata.json"

    @property
    def chunks(self) -> Path:
        return self.rag / "rag_chunks.json"

    @property
    def embeddings(self) -> Path:
        return self.rag / "embeddings.npy"

    @property
    def business_v2(self) -> Path:
        return self.profile / "business_v2" / "business_profile_v2.json"

    @property
    def company_profile(self) -> Path:
        return self.profile / "company_profile_v2.json"

    @property
    def finance_latest(self) -> Path:
        return self.finance / "finance_latest.json"

    @property
    def finance_metrics(self) -> Path:
        return self.finance / "finance_metrics.json"

    @property
    def unified(self) -> Path:
        return self.profile / UNIFIED_FILENAME


# ============================================================
# JSON / 상태 파일
# ============================================================


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    temporary.replace(path)


def load_state(paths: Paths, params: dict) -> dict:
    """이전 실행과 설정(회사/기준일)이 다르면 중단한다. 산출물이 섞이면 누수가 생기기 때문이다."""
    state = load_json(paths.state)
    if state is None:
        return {"params": params, "steps": {}}
    if state.get("params") != params:
        raise SystemExit(
            "이전 실행과 설정이 다릅니다.\n"
            f"  이전: {state.get('params')}\n"
            f"  현재: {params}\n"
            "같은 폴더에 다른 기준일의 산출물이 섞이지 않도록 중단합니다.\n"
            f"기존 산출물을 다른 곳으로 옮기고 {paths.state} 를 지운 뒤 다시 실행하세요."
        )
    return state


# ============================================================
# 단계 정의
# ============================================================


def python_script(name: str, *args: str) -> list[str]:
    return [sys.executable, str(ROOT_DIR / "scripts" / name), *args]


def build_steps(paths: Paths, params: dict, corp_code: str | None) -> dict[str, dict]:
    company = params["company"]
    cutoff = params["cutoff"]
    corp = corp_code or "<corp_code>"
    finance_raw = paths.finance / "raw"

    return {
        "download": {
            "cmd": python_script("download_company_reports.py"),
            "stdin": f"{company}\n{params['stock_code']}\n{params.get('corp_code') or ''}\n{params['ipo_date']}\n",
            "needs": "DART_API_KEY",
        },
        "preprocess": {
            "cmd": python_script("preprocess_company_reports.py"),
            "stdin": f"{company}\n",
        },
        "evidence": {
            "cmd": python_script("build_business_profile.py"),
            "stdin": f"{company}\n",
        },
        "chunks": {
            "cmd": python_script("build_rag_chunks.py"),
            "stdin": f"{company}\n",
        },
        "embeddings": {
            # 임베딩이 없을 때만 생성하고, 이어지는 질의 루프는 q로 즉시 종료한다.
            "cmd": python_script("test_profile_rag.py"),
            "stdin": f"{company}\nq\n",
            "needs": "BGE-M3 모델(GPU 권장)",
        },
        "enrich": {
            "cmd": python_script(
                "business_metadata_enricher.py", "--company", company, "--corp-code", corp
            ),
            "stdin": None,
        },
        "business_v2": {
            "cmd": python_script(
                "generate_business_profile_v2.py",
                "--company", company,
                "--corp-code", corp,
                "--analysis-as-of", cutoff,
            ),
            "stdin": None,
            "needs": "LLM_API_KEY",
        },
        "growth": {
            "cmd": python_script("generate_company_profile.py"),
            "stdin": f"{company}\n3\n",
            "needs": "LLM_API_KEY",
        },
        "risk": {
            "cmd": python_script("generate_company_profile.py"),
            "stdin": f"{company}\n4\n",
            "needs": "LLM_API_KEY",
        },
        "fin_download": {
            "cmd": python_script("download_financial_statements.py"),
            "stdin": f"{company}\n",
            "needs": "DART_API_KEY",
        },
        "fin_profile": {
            "cmd": python_script("build_finance_profile.py"),
            "stdin": f"{company}\n",
        },
        "fin_latest": {
            "cmd": [
                sys.executable, "-m", "peerproof.finance.finance_latest",
                str(finance_raw),
                "--output", str(paths.finance_latest),
                "--as-of", cutoff,
            ],
            "stdin": None,
        },
        "fin_metrics": {
            "cmd": [
                sys.executable, "-m", "peerproof.finance.finance_metrics",
                str(paths.finance_latest),
                "--output", str(paths.finance_metrics),
            ],
            "stdin": None,
        },
    }


def outputs_ready(key: str, paths: Paths, params: dict) -> bool:
    """상태 파일이 '완료'라고 해도 산출물이 실제로 있어야 완료로 본다."""
    if key == "download":
        meta = load_json(paths.raw_metadata)
        return bool(meta) and meta.get("collection_rule", {}).get("ipo_date") == params["ipo_date"]
    if key == "preprocess":
        return (paths.processed / "processed_metadata.json").exists()
    if key == "evidence":
        return (paths.profile / "profile_evidence.json").exists()
    if key == "chunks":
        return paths.chunks.exists()
    if key == "embeddings":
        return embeddings_aligned(paths)
    if key == "business_v2":
        return business_v2_complete(paths)
    if key == "fin_download":
        return any((paths.finance / "raw").glob("*.json"))
    if key == "fin_profile":
        return (paths.finance / "finance_profile.json").exists()
    if key == "fin_latest":
        return paths.finance_latest.exists()
    if key == "fin_metrics":
        return paths.finance_metrics.exists()
    if key == "enrich":
        # 보강 여부를 산출물만으로는 알 수 없다. Business v2가 만들어졌다면 보강 이후 단계까지 간 것이다.
        return paths.business_v2.exists()
    if key in ("growth", "risk"):
        profile = (load_json(paths.company_profile, {}) or {}).get("profile", {})
        return bool(profile.get(key))
    return True


def chunk_count(paths: Paths) -> int | None:
    data = load_json(paths.chunks)
    if isinstance(data, dict) and isinstance(data.get("chunks"), list):
        return len(data["chunks"])
    if isinstance(data, list):
        return len(data)
    return None


def embeddings_aligned(paths: Paths) -> bool:
    """embeddings.npy의 행 수가 rag_chunks.json의 chunk 수와 같아야 한다."""
    if not paths.embeddings.exists():
        return False
    expected = chunk_count(paths)
    if expected is None:
        return False
    try:
        import numpy as np

        return int(np.load(paths.embeddings, mmap_mode="r").shape[0]) == expected
    except Exception:
        return False


def business_v2_complete(paths: Paths) -> bool:
    data = load_json(paths.business_v2)
    if not data:
        return False
    summary = data.get("summary", {})
    return bool(summary) and summary.get("completed_features") == summary.get("total_features")


# ============================================================
# 통합 프로필 조립 + 기준일 누수 점검
# ============================================================

FINANCE_ACCOUNTS = [
    ("revenue", "매출액"),
    ("operating_income", "영업이익"),
    ("net_income_parent", "지배주주 순이익"),
    ("net_income_total", "전체 순이익"),
    ("total_assets", "자산총계"),
    ("total_liabilities", "부채총계"),
    ("total_equity", "자본총계"),
    ("equity_parent", "지배주주 자본"),
    ("operating_cash_flow", "영업현금흐름"),
]


def iter_fields(section: Any):
    if isinstance(section, dict):
        for key, value in section.items():
            if isinstance(value, dict) and ("status" in value or "value" in value):
                yield key, value


def count_status(section: Any) -> dict:
    counts: dict[str, int] = {}
    total = 0
    for _, field in iter_fields(section):
        total += 1
        status = str(field.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {"total": total, "by_status": counts}


def chunk_sources(paths: Paths) -> dict[str, dict]:
    """chunk_id -> 공시 출처(rcept_no, filing_date). rag_chunks.json이 출처의 원본이다."""
    chunks = load_json(paths.chunks, []) or []
    if isinstance(chunks, dict):
        chunks = chunks.get("chunks", [])
    return {
        c["chunk_id"]: {"rcept_no": c.get("rcept_no"), "filing_date": c.get("filing_date")}
        for c in chunks
        if isinstance(c, dict) and c.get("chunk_id") and c.get("filing_date")
    }


def item_source(item: Any, sources: dict[str, dict]) -> dict | None:
    """근거 하나의 출처. 근거 자체의 source가 우선, 없으면 chunk_id로 보충한다."""
    if not isinstance(item, dict):
        return None
    own = item.get("source")
    if isinstance(own, dict) and own.get("filing_date"):
        return own
    return sources.get(item.get("chunk_id"))


def collect_evidence_dates(sources: dict[str, dict], *sections: Any) -> list[dict]:
    found = []
    for section in sections:
        for key, field in iter_fields(section):
            for item in field.get("evidence") or []:
                source = item_source(item, sources)
                if source:
                    found.append(
                        {
                            "field": key,
                            "evidence_id": item.get("evidence_id"),
                            "filing_date": source["filing_date"],
                            "rcept_no": source.get("rcept_no"),
                        }
                    )
    return found


def count_evidence_without_date(sources: dict[str, dict], *sections: Any) -> int:
    """공시일(provenance)이 없어 개별로는 기준일 점검이 안 되는 근거 수."""
    missing = 0
    for section in sections:
        for _, field in iter_fields(section):
            for item in field.get("evidence") or []:
                if not item_source(item, sources):
                    missing += 1
    return missing


def leakage_check(
    paths: Paths,
    cutoff: str,
    selected: dict,
    evidence: list[dict],
    evidence_without_date: int = 0,
) -> dict:
    cutoff_compact = compact(cutoff)
    violations = []

    for report_type, report in (selected or {}).items():
        date = str(report.get("rcept_date") or "")
        if date and date > cutoff_compact:
            violations.append(
                {"kind": "selected_report_after_cutoff", "report_type": report_type, "rcept_date": date}
            )

    allowed_rcept = {str(r.get("rcept_no")) for r in (selected or {}).values()}
    for item in evidence:
        if compact(str(item["filing_date"])) > cutoff_compact:
            violations.append({"kind": "evidence_after_cutoff", **item})
        elif item.get("rcept_no") and allowed_rcept and str(item["rcept_no"]) not in allowed_rcept:
            violations.append({"kind": "evidence_report_not_selected", **item})

    extra_dirs = []
    if paths.processed.exists():
        for child in paths.processed.iterdir():
            if child.is_dir() and child.name not in (*REPORT_TYPES, "profile", "rag", "finance"):
                extra_dirs.append(child.name)

    return {
        "cutoff": cutoff,
        "selected_report_count": len(selected or {}),
        "evidence_checked": len(evidence),
        "evidence_without_filing_date": evidence_without_date,
        "violations": violations,
        "unexpected_processed_dirs": extra_dirs,
        "passed": not violations,
    }


import re as _re

UNIT_MULTIPLIER = {"원": 1, "천원": 1_000, "백만원": 1_000_000, "억원": 100_000_000}
_NUM = r"(-|[\d,]+)"


def _to_number(text: str) -> int:
    return 0 if text.strip() == "-" else int(text.replace(",", ""))


def parse_sales_table(content: str) -> dict | None:
    """'매출실적' 표의 합계 블록에서 당기 내수/수출/계를 읽는다. 읽지 못하면 None."""
    flat = " ".join(content.split())
    unit = _re.search(r"\(단위\s*:\s*([^)]+)\)", flat)
    multiplier = UNIT_MULTIPLIER.get(unit.group(1).strip()) if unit else None
    block = _re.search(r"합계\s*\|\s*(?:내수|국내)\s*\|(.*)", flat)
    if not multiplier or not block:
        return None
    tail = "합계 | 내수 |" + block.group(1)
    tail = tail.split("※")[0]
    domestic = _re.search(r"(?:내수|국내)\s*\|\s*" + _NUM, tail)
    export = _re.search(r"(?:수출|해외)\s*\|\s*" + _NUM, tail)
    total = _re.search(r"\|\s*계\s*\|\s*" + _NUM, tail)
    if not (domestic and export and total):
        return None
    return {
        "domestic": _to_number(domestic.group(1)) * multiplier,
        "overseas": _to_number(export.group(1)) * multiplier,
        "total": _to_number(total.group(1)) * multiplier,
    }


def growth_metrics(paths: Paths, finance_company: dict, cutoff: str) -> dict:
    """G1~G4를 규칙으로 계산한다(LLM 없음). 근거를 못 찾으면 값을 비우고 이유를 남긴다."""
    context = finance_company.get("context") or {}
    revenue_account = (finance_company.get("accounts") or {}).get("revenue") or {}
    revenue = revenue_account.get("value")
    source = {
        "rcept_no": context.get("rcept_no"),
        "filing_date": context.get("rcept_date"),
        "period": f"{context.get('period_start')} ~ {context.get('period_end')}",
    }

    def metric(value, status, note=None, src=None):
        return {"value": value, "status": status, "source": src or source, "note": note}

    result = {
        "revenue": metric(revenue, "확인" if revenue is not None else "미확인",
                          None if revenue is not None else "finance_latest에 매출이 없음"),
    }

    previous = None
    finance_profile = load_json(paths.finance / "finance_profile.json", {}) or {}
    latest = (finance_profile.get("periods") or {}).get(finance_profile.get("latest_period"), {})
    previous_account = (latest.get("accounts") or {}).get("revenue") or {}
    if previous_account.get("status") == "found":
        previous = previous_account.get("previous_value")
    result["previous_period_revenue"] = metric(
        previous, "확인" if previous is not None else "미확인",
        "전년 동기(누적) 매출. finance_profile의 previous_value" if previous is not None
        else "finance_profile에서 전년 동기 매출을 찾지 못함",
    )
    if revenue and previous:
        result["revenue_growth_rate"] = metric(round(revenue / previous - 1, 4), "확인", "전년 동기 대비")
    else:
        result["revenue_growth_rate"] = metric(None, "미확인", "매출 또는 전년 동기 매출 없음")

    table, table_source = None, None
    chunks = load_json(paths.chunks, []) or []
    if isinstance(chunks, dict):
        chunks = chunks.get("chunks", [])
    candidates = [
        c for c in chunks
        if isinstance(c, dict)
        and "매출실적" in str(c.get("section") or "")
        and str(c.get("filing_date") or "9999") <= cutoff
        and c.get("rcept_no") == context.get("rcept_no")
    ]
    for chunk in candidates:
        parsed = parse_sales_table(chunk.get("content") or "")
        if parsed:
            table = parsed
            table_source = {
                "rcept_no": chunk.get("rcept_no"),
                "filing_date": chunk.get("filing_date"),
                "period": chunk.get("period"),
                "chunk_id": chunk.get("chunk_id"),
                "section": chunk.get("section"),
            }
            break

    if not table:
        reason = "최신 보고서의 매출실적 표(내수/수출/계)를 읽지 못함"
        result["overseas_revenue"] = metric(None, "미확인", reason)
        result["overseas_revenue_ratio"] = metric(None, "미확인", reason)
        return result

    consistent = bool(revenue) and abs(table["total"] - revenue) / revenue <= 0.005
    status = "확인" if consistent else "부분확인"
    note = "매출실적 표 합계 수출 (표 합계와 재무제표 매출 일치)" if consistent else \
        "매출실적 표 합계가 재무제표 매출과 0.5% 넘게 달라 검토 필요"
    result["overseas_revenue"] = metric(table["overseas"], status, note, table_source)
    base = revenue if consistent else table["total"]
    result["overseas_revenue_ratio"] = metric(
        round(table["overseas"] / base, 4) if base else None, status,
        "해외(수출) 매출 / 총매출", table_source,
    )
    return result


def assemble(paths: Paths, params: dict, corp_code: str | None) -> dict:
    cutoff = params["cutoff"]
    raw_meta = load_json(paths.raw_metadata, {}) or {}
    corp_code = corp_code or raw_meta.get("company", {}).get("corp_code")
    selected = raw_meta.get("selected_reports", {})

    business_v2 = load_json(paths.business_v2, {}) or {}
    legacy = load_json(paths.company_profile, {}) or {}
    legacy_profile = legacy.get("profile", {}) if isinstance(legacy, dict) else {}

    business_model = business_v2.get("business", {})
    growth = legacy_profile.get("growth", {})
    risk = legacy_profile.get("risk", {})

    finance_doc = load_json(paths.finance_latest, {}) or {}
    companies = finance_doc.get("companies", {}) if isinstance(finance_doc, dict) else {}
    finance_company = companies.get(corp_code) or (next(iter(companies.values()), {}) if companies else {})
    accounts = finance_company.get("accounts", {})

    financial_raw = {}
    for key, label in FINANCE_ACCOUNTS:
        account = accounts.get(key)
        financial_raw[key] = {
            "label": label,
            "value": account.get("value") if isinstance(account, dict) else None,
            "status": account.get("status") if isinstance(account, dict) else "missing",
        }

    metrics = growth_metrics(paths, finance_company, cutoff)
    sources = chunk_sources(paths)
    evidence = collect_evidence_dates(sources, business_model, growth, risk)
    check = leakage_check(
        paths,
        cutoff,
        selected,
        evidence,
        count_evidence_without_date(sources, business_model, growth, risk),
    )

    completeness = {
        "business_model": count_status(business_model),
        "growth": count_status(growth),
        "risk": count_status(risk),
        "financial_raw": {
            "total": len(financial_raw),
            "available": sum(1 for v in financial_raw.values() if v["value"] is not None),
        },
    }

    unified = {
        "schema_version": UNIFIED_SCHEMA,
        "company": {
            "company_name": params["company"],
            "stock_code": params["stock_code"],
            "corp_code": corp_code,
        },
        "analysis_as_of": cutoff,
        "ipo_date": params["ipo_date"],
        "built_at": datetime.now().astimezone().isoformat(),
        "source_reports": selected,
        "business_model": business_model,
        "growth": growth,
        "growth_metrics": metrics,
        "risk": risk,
        "financial_raw": {"period_context": finance_company.get("context"), "accounts": financial_raw},
        "completeness": completeness,
        "leakage_check": check,
        "inputs": {
            "business_v2": str(paths.business_v2.relative_to(paths.root)) if paths.business_v2.exists() else None,
            "company_profile": str(paths.company_profile.relative_to(paths.root)) if paths.company_profile.exists() else None,
            "finance_latest": str(paths.finance_latest.relative_to(paths.root)) if paths.finance_latest.exists() else None,
        },
    }
    save_json(paths.unified, unified)
    return unified


def print_report(unified: dict, output_path: Path) -> None:
    print()
    print("=" * 70)
    print(f"통합 프로필: {unified['company']['company_name']}  (기준일 {unified['analysis_as_of']})")
    print("=" * 70)
    completeness = unified["completeness"]
    for section in ("business_model", "growth", "risk"):
        item = completeness[section]
        print(f"  {section:<15} {item['total']:>2}개 항목  {item['by_status']}")
    metrics = unified.get("growth_metrics") or {}
    if metrics:
        confirmed = sum(1 for m in metrics.values() if m["value"] is not None)
        print(f"  {'growth_metrics':<15} {confirmed}/{len(metrics)}개 값 (매출·전년동기·성장률·해외매출·해외비중)")
    fin = completeness["financial_raw"]
    print(f"  {'financial_raw':<15} {fin['available']}/{fin['total']} 계정")
    check = unified["leakage_check"]
    print()
    print(
        f"기준일 누수 점검: {'통과' if check['passed'] else '실패'} "
        f"(선택 보고서 {check['selected_report_count']}건, 근거 {check['evidence_checked']}건 확인)"
    )
    if check["evidence_without_filing_date"]:
        print(
            f"  참고: 공시일 정보가 없는 근거 {check['evidence_without_filing_date']}건은 "
            "개별 점검이 안 됩니다(선택된 보고서가 모두 cutoff 이전이므로 색인 수준에서는 안전)."
        )
    for violation in check["violations"]:
        print(f"  ! {violation}")
    if check["unexpected_processed_dirs"]:
        print(f"  ! 예상 밖 폴더: {check['unexpected_processed_dirs']}")
    print(f"저장: {output_path}")


# ============================================================
# 실행
# ============================================================


def run_step(key: str, spec: dict, env: dict) -> int:
    print()
    print("-" * 70)
    print(f"[{key}] {' '.join(spec['cmd'][1:3])} ...")
    print("-" * 70)
    result = subprocess.run(
        spec["cmd"],
        input=spec["stdin"],
        text=True,
        cwd=ROOT_DIR,
        env=env,
    )
    return result.returncode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PeerProof 공통 프로필 생성 파이프라인")
    parser.add_argument("--company", required=True, help='기업명 (예: "에이피알")')
    parser.add_argument("--corp-code", default="", help="DART 고유번호 8자리. 주면 종목코드/기업명보다 우선해 기업을 찾는다(미상장 기업에 권장).")
    parser.add_argument("--stock-code", default="", help="종목코드 (예: 278470). 미상장 기업은 생략하면 기업명으로 찾는다.")
    when = parser.add_mutually_exclusive_group(required=True)
    when.add_argument("--as-of", help="분석 기준일 YYYYMMDD. 이 날짜까지 접수된 공시만 사용한다.")
    when.add_argument("--ipo-date", help="(이전 이름) IPO 기준일 YYYYMMDD. 분석 기준일은 그 전날이다.")
    parser.add_argument("--from-step", choices=STEP_KEYS, default=STEP_KEYS[0])
    parser.add_argument("--to-step", choices=STEP_KEYS, default=STEP_KEYS[-1])
    parser.add_argument("--force", action="store_true", help="완료된 단계도 다시 실행")
    parser.add_argument("--dry-run", action="store_true", help="실행하지 않고 계획만 출력")
    parser.add_argument("--assemble-only", action="store_true", help="통합 프로필 조립과 누수 점검만 실행")
    parser.add_argument(
        "--adopt-existing",
        action="store_true",
        help="이미 산출물이 있는 단계를 실행하지 않고 완료로 인정(LLM 재호출 방지)",
    )
    parser.add_argument("--root", type=Path, default=ROOT_DIR, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    global ROOT_DIR
    args = parse_args(argv)
    ROOT_DIR = args.root.resolve()

    if args.as_of:
        try:
            as_of = datetime.strptime(args.as_of, "%Y%m%d")
        except ValueError:
            raise SystemExit(f"--as-of는 YYYYMMDD 형식이어야 합니다: {args.as_of}")
        # 기존 단계 스크립트는 'IPO 기준일'(=분석 기준일 다음 날)을 입력으로 받는다.
        ipo_date = (as_of + timedelta(days=1)).strftime("%Y%m%d")
    else:
        ipo_date = args.ipo_date
    cutoff = compute_cutoff(ipo_date)
    params = {
        "company": args.company,
        "stock_code": args.stock_code,
        "ipo_date": ipo_date,
        "cutoff": cutoff,
    }
    paths = Paths(ROOT_DIR, args.company)

    if args.assemble_only:
        unified = assemble(paths, params, None)
        print_report(unified, paths.unified)
        return 0 if unified["leakage_check"]["passed"] else 2

    state = load_state(paths, params)

    if args.adopt_existing:
        adopted = []
        for key in STEP_KEYS[:-1]:
            if key not in state["steps"] and outputs_ready(key, paths, params):
                state["steps"][key] = {"adopted": True, "at": datetime.now().astimezone().isoformat()}
                adopted.append(key)
        if adopted and not args.dry_run:
            save_json(paths.state, state)
        print(f"기존 산출물을 완료로 인정한 단계: {adopted or '없음'}")
    first = STEP_KEYS.index(args.from_step)
    last = STEP_KEYS.index(args.to_step)
    selected_keys = STEP_KEYS[first : last + 1]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"

    print(f"기업: {args.company} ({args.stock_code or '종목코드 없음'}"
          + (f", corp_code {args.corp_code}" if args.corp_code else "") + ")")
    print(f"분석 기준일(cutoff): {cutoff}  (내부 IPO 기준일 값: {ipo_date})")
    print("cutoff 이후에 접수된 공시는 사용하지 않습니다.")

    corp_code = (load_json(paths.raw_metadata, {}) or {}).get("company", {}).get("corp_code")

    for key in selected_keys:
        if key == "assemble":
            continue

        if key == "embeddings" and paths.embeddings.exists() and not embeddings_aligned(paths):
            stale = paths.embeddings.with_suffix(".npy.stale")
            if not args.dry_run:
                paths.embeddings.replace(stale)
            print(f"[embeddings] chunk 수와 맞지 않는 기존 파일을 {stale.name}으로 옮깁니다.")

        # corp_code는 기업을 찾는 방법일 뿐 산출물의 조건이 아니라 상태 비교(params)에는 넣지 않는다.
        steps = build_steps(paths, {**params, "corp_code": args.corp_code}, corp_code)
        spec = steps[key]
        done = (
            key in state["steps"]
            and outputs_ready(key, paths, params)
            and not args.force
        )

        if args.dry_run:
            status = "완료(건너뜀)" if done else "실행"
            need = f"  필요: {spec['needs']}" if spec.get("needs") else ""
            print(f"  [{status}] {key}{need}")
            continue

        if done:
            print(f"[건너뜀] {key} (이미 완료)")
            continue

        code = run_step(key, spec, env)
        if code != 0:
            print(f"\n[{key}] 단계가 실패했습니다 (종료 코드 {code}). 원인을 해결하고 같은 명령을 다시 실행하면 이 단계부터 이어집니다.")
            return code

        if key in ("download", "preprocess", "evidence", "chunks", "embeddings", "business_v2", "fin_download", "fin_latest", "fin_metrics") and not outputs_ready(key, paths, params):
            print(f"\n[{key}] 단계는 끝났지만 예상한 산출물이 없습니다. 위 출력을 확인하세요.")
            return 3

        state["steps"][key] = {"done_at": datetime.now().astimezone().isoformat()}
        save_json(paths.state, state)

        if key == "download":
            corp_code = (load_json(paths.raw_metadata, {}) or {}).get("company", {}).get("corp_code")
            if not corp_code:
                print("raw metadata.json에서 corp_code를 찾지 못했습니다.")
                return 3

    if "assemble" in selected_keys and not args.dry_run:
        unified = assemble(paths, params, corp_code)
        state["steps"]["assemble"] = {"done_at": datetime.now().astimezone().isoformat()}
        save_json(paths.state, state)
        print_report(unified, paths.unified)
        return 0 if unified["leakage_check"]["passed"] else 2

    return 0


if __name__ == "__main__":
    sys.exit(main())