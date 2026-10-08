from __future__ import annotations

"""
PeerProof Business metadata enricher
===================================

목적
----
Business Profile RAG의 provenance metadata를 보강한다.
기존 Business Feature Logic(schema.py)은 건드리지 않고, 아래 경로의 metadata를 연결한다.

    DART raw metadata
        -> processed/{company}/{report_type}/metadata.json
        -> profile/profile_evidence.json  (business evidence only)
        -> rag/rag_chunks.json            (business chunks only)

주요 필드
---------
- report / report_name / report_type
- rcept_no
- filing_date
- period / period_start / period_end / period_type
- section
- page
- source_zip / source_document

설계 원칙
---------
1) DART/raw에 이미 있는 값은 재추정하지 않고 우선 사용한다.
2) 기간은 report_name만 보고 추정하지 않고 document.md의 '사업연도 ... 부터/까지'를 우선 읽는다.
3) quarterly라는 문서명만으로 단일분기라고 보지 않는다. 시작일이 1월 1일이면 YTD로 기록한다.
4) section/page는 document.md의 본문 heading과 목차(TOC)를 이용해 best-effort로 붙인다.
5) page를 안정적으로 찾지 못하면 None을 유지한다. 임의 페이지를 생성하지 않는다.
6) business category만 evidence/chunk를 수정한다. growth/risk/finance는 건드리지 않는다.

사용 예
-------
프로젝트 루트에서:

    python scripts/enrich_business_metadata.py --company "에이피알"

이 파일을 scripts/enrich_business_metadata.py 로 두고 사용해도 되고,
현재 위치에서 --project-root를 지정해 실행해도 된다.
"""

import argparse
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


REPORT_TYPES = ("annual", "semiannual", "quarterly")
METADATA_VERSION = "business-provenance-v1.0"


# -----------------------------------------------------------------------------
# JSON helpers
# -----------------------------------------------------------------------------

def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


# -----------------------------------------------------------------------------
# String/date helpers
# -----------------------------------------------------------------------------

def normalize_space(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u200b", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_for_match(text: str) -> str:
    text = normalize_space(text)
    # Markdown table syntax/comment는 의미 매칭에서 방해되므로 약화
    text = re.sub(r"<!--\s*table_\d+\s*-->", " ", text, flags=re.I)
    text = text.replace("|", " ")
    text = re.sub(r"[-]{3,}", " ", text)
    return normalize_space(text).lower()


def iso_date(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != 8:
        return None
    try:
        return datetime.strptime(digits, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def korean_date_to_iso(text: str) -> str | None:
    m = re.search(
        r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일",
        text or "",
    )
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    try:
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def compact_date(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("-", "")


# -----------------------------------------------------------------------------
# Report provenance
# -----------------------------------------------------------------------------

@dataclass
class ReportProvenance:
    report_type: str
    report_name: str | None = None
    rcept_no: str | None = None
    filing_date: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    period_type: str | None = None
    source_zip: str | None = None
    source_document: str | None = None

    @property
    def period(self) -> str | None:
        if self.period_start and self.period_end:
            return f"{self.period_start} ~ {self.period_end}"
        if self.period_end:
            return self.period_end
        return None

    def to_metadata(self) -> dict[str, Any]:
        d = asdict(self)
        d["report"] = self.report_name or self.report_type
        d["period"] = self.period
        return d


def parse_period_from_document(document_md: str) -> tuple[str | None, str | None]:
    """DART 본문 앞부분의 '사업연도 YYYY년..부터 / ...까지'를 최우선 사용."""
    head = document_md[:8000]

    # 대부분의 DART 정기보고서는 첫 표에 두 날짜가 연속으로 등장한다.
    # '사업연도' 이후 범위를 제한해 다른 날짜(제출일 등) 오탐을 줄인다.
    pos = head.find("사업연도")
    target = head[pos : pos + 1200] if pos >= 0 else head[:1200]

    dates = re.findall(
        r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일",
        target,
    )

    if len(dates) >= 2:
        out = []
        for y, mo, d in dates[:2]:
            try:
                out.append(datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d"))
            except ValueError:
                out.append(None)
        return out[0], out[1]

    return None, None


def infer_period_from_report_name(report_name: str | None, report_type: str) -> tuple[str | None, str | None]:
    """document.md에서 기간을 못 찾았을 때만 쓰는 fallback."""
    if not report_name:
        return None, None

    m = re.search(r"\((20\d{2})\.(\d{1,2})\)", report_name)
    if not m:
        return None, None

    year, month = map(int, m.groups())
    start = f"{year:04d}-01-01"

    # 월말 계산: 다음 달 1일 - 1일 대신 표준 library만 사용해 간단히 계산
    if month == 12:
        end = f"{year:04d}-12-31"
    else:
        from datetime import date, timedelta
        next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        last_day = next_month - timedelta(days=1)
        end = last_day.isoformat()

    return start, end


def classify_period_type(report_type: str, start: str | None, end: str | None) -> str | None:
    if not start or not end:
        return None

    try:
        s = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end, "%Y-%m-%d")
    except ValueError:
        return None

    if s.month == 1 and s.day == 1 and e.month == 12 and e.day == 31:
        return "FY"

    if s.month == 1 and s.day == 1:
        return "YTD"

    if report_type == "quarterly":
        return "QUARTER"

    return "PERIOD"


def parse_rcept_from_source_zip(source_zip: str | None) -> tuple[str | None, str | None]:
    if not source_zip:
        return None, None
    # 20231114_quarterly_20231114001221_분기보고서 (2023.09).zip
    m = re.match(r"(20\d{6})_[^_]+_(\d{14})_", source_zip)
    if not m:
        return None, None
    filing_date = iso_date(m.group(1))
    return m.group(2), filing_date


def build_report_provenance(
    report_type: str,
    raw_selected: dict[str, Any],
    processed_report_dir: Path,
) -> ReportProvenance:
    selected = raw_selected.get(report_type) or {}
    processed_meta_path = processed_report_dir / "metadata.json"
    processed_meta = load_json(processed_meta_path, {})
    document_md = read_text(processed_report_dir / "document.md")

    report_name = selected.get("report_name") or processed_meta.get("report_name")
    rcept_no = selected.get("rcept_no") or processed_meta.get("rcept_no")
    filing_date = iso_date(selected.get("rcept_date") or selected.get("filing_date"))

    if not rcept_no or not filing_date:
        zip_rcept, zip_date = parse_rcept_from_source_zip(processed_meta.get("source_zip"))
        rcept_no = rcept_no or zip_rcept
        filing_date = filing_date or zip_date

    period_start, period_end = parse_period_from_document(document_md)
    if not (period_start and period_end):
        fallback_start, fallback_end = infer_period_from_report_name(report_name, report_type)
        period_start = period_start or fallback_start
        period_end = period_end or fallback_end

    period_type = classify_period_type(report_type, period_start, period_end)

    return ReportProvenance(
        report_type=report_type,
        report_name=report_name,
        rcept_no=rcept_no,
        filing_date=filing_date,
        period_start=period_start,
        period_end=period_end,
        period_type=period_type,
        source_zip=processed_meta.get("source_zip"),
        source_document=processed_meta.get("source_document"),
    )


# -----------------------------------------------------------------------------
# Section / page parsing
# -----------------------------------------------------------------------------

@dataclass
class SectionSegment:
    section: str | None
    page: int | None
    text: str


def clean_toc_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value


def parse_toc_pages(document_md: str) -> dict[str, int]:
    """목차 Markdown table에서 '제목 -> DART page'를 추출한다."""
    toc: dict[str, int] = {}

    # 목차는 본문 시작 전 앞부분에 존재한다.
    head = document_md[:25000]
    for line in head.splitlines():
        if not line.lstrip().startswith("|"):
            continue

        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue

        title = clean_toc_title(cells[0])
        if not title or set(title) <= {"-", ":", " "}:
            continue

        # 마지막 숫자 cell을 page로 본다.
        page = None
        for cell in reversed(cells[1:]):
            m = re.fullmatch(r"\d{1,4}", cell)
            if m:
                page = int(cell)
                break

        if page is not None:
            toc[title] = page

    return toc


def heading_info(paragraph: str) -> tuple[int | None, str | None]:
    """DART 본문의 section heading을 보수적으로 판별한다."""
    p = normalize_space(paragraph)
    if not p:
        return None, None

    # 표/주석/목차행은 heading으로 보지 않는다.
    if p.startswith("|") or p.startswith("<!--"):
        return None, None

    # I. / II. / XII.
    m = re.match(r"^([IVX]+\.\s*[^\n|]{1,100})$", p)
    if m:
        return 1, m.group(1).strip()

    # 1. / 7-1. 등. 제목 단독인 경우를 우선.
    m = re.match(r"^(\d+(?:-\d+)?\.\s*[^\n|]{1,100})$", p)
    if m:
        return 2, m.group(1).strip()

    # '가. 매출실적', '나. 판매경로 및 판매방법(1) 판매경로' 등
    # 본문이 같은 paragraph에 이어질 수 있으므로 첫 100자까지만 heading 후보로 사용.
    m = re.match(r"^([가-힣]\.\s*[^\n|]{1,100}?)(?=(?:\(\d+\)|\s{2,}|$))", p)
    if m:
        title = m.group(1).strip()
        # 너무 긴 일반문장 오탐 방지
        if len(title) <= 100:
            return 3, title

    # (1) 판매경로 등
    m = re.match(r"^(\(\d+\)\s*[^\n|]{1,100})$", p)
    if m:
        return 4, m.group(1).strip()

    return None, None


def page_for_section(levels: dict[int, str], toc: dict[str, int]) -> int | None:
    # 가장 구체적인 heading부터 정확/부분 일치 시도
    for level in (4, 3, 2, 1):
        title = levels.get(level)
        if not title:
            continue
        if title in toc:
            return toc[title]

        # 소제목은 목차에 없을 수 있으므로 괄호 이하를 제거한 후보도 시도
        simplified = re.sub(r"\(\d+\).*?$", "", title).strip()
        if simplified in toc:
            return toc[simplified]

    return None


def build_section_segments(document_md: str) -> list[SectionSegment]:
    """본문을 section path 단위로 묶는다."""
    toc = parse_toc_pages(document_md)
    paragraphs = [p for p in re.split(r"\n\s*\n", document_md) if normalize_space(p)]

    levels: dict[int, str] = {}
    grouped: list[SectionSegment] = []

    # 목차 자체가 본문 section으로 오인되지 않도록 실제 본문 시작 이후를 선호한다.
    # 대표이사 확인 뒤 처음 등장하는 'I. 회사의 개요'가 안전한 시작점이다.
    body_started = False

    for paragraph in paragraphs:
        norm = normalize_space(paragraph)

        if norm == "I. 회사의 개요":
            body_started = True

        if not body_started:
            continue

        level, title = heading_info(paragraph)
        if level and title:
            levels[level] = title
            for deeper in range(level + 1, 5):
                levels.pop(deeper, None)

        section_parts = [levels[k] for k in sorted(levels) if levels.get(k)]
        section = " > ".join(section_parts) if section_parts else None
        page = page_for_section(levels, toc)

        if grouped and grouped[-1].section == section and grouped[-1].page == page:
            grouped[-1].text += "\n" + paragraph
        else:
            grouped.append(SectionSegment(section=section, page=page, text=paragraph))

    return grouped


def token_set(text: str) -> set[str]:
    return set(re.findall(r"[0-9A-Za-z가-힣]{2,}", normalize_for_match(text)))


def locate_section(content: str, segments: list[SectionSegment]) -> tuple[str | None, int | None]:
    """chunk/evidence 내용과 가장 가까운 본문 section을 찾는다."""
    if not content or not segments:
        return None, None

    target = normalize_for_match(content)
    if not target:
        return None, None

    # 1) 앞부분 exact substring: 가장 신뢰도가 높다.
    anchor = target[:180]
    if len(anchor) >= 30:
        for seg in segments:
            seg_norm = normalize_for_match(seg.text)
            if anchor in seg_norm:
                return seg.section, seg.page

    # 2) chunk 전체가 section text에 포함되는 경우
    short_target = target[:700]
    for seg in segments:
        seg_norm = normalize_for_match(seg.text)
        if len(short_target) >= 40 and short_target in seg_norm:
            return seg.section, seg.page

    # 3) token overlap fallback. 낮은 신뢰도는 metadata를 만들지 않는다.
    target_tokens = token_set(content)
    if not target_tokens:
        return None, None

    best_score = 0.0
    best: SectionSegment | None = None

    for seg in segments:
        seg_tokens = token_set(seg.text)
        if not seg_tokens:
            continue
        overlap = len(target_tokens & seg_tokens)
        score = overlap / max(1, min(len(target_tokens), 50))
        if score > best_score:
            best_score = score
            best = seg

    if best is not None and best_score >= 0.22:
        return best.section, best.page

    return None, None


# -----------------------------------------------------------------------------
# Project path resolution
# -----------------------------------------------------------------------------

def find_company_dir(root: Path, company: str, corp_code: str | None, metadata_name: str) -> Path:
    direct = root / company
    if direct.exists():
        return direct

    # 압축 해제/인코딩 환경에서도 corp_name/corp_code로 찾아갈 수 있게 fallback 제공
    for child in root.iterdir() if root.exists() else []:
        if not child.is_dir():
            continue
        meta_path = child / metadata_name
        if not meta_path.exists():
            continue
        meta = load_json(meta_path, {})
        company_meta = meta.get("company", {})
        if company_meta.get("corp_name") == company:
            return child
        if corp_code and company_meta.get("corp_code") == corp_code:
            return child

    raise FileNotFoundError(f"기업 폴더를 찾지 못했습니다: root={root}, company={company}")


# -----------------------------------------------------------------------------
# Enrichment
# -----------------------------------------------------------------------------

def enrich_report_metadata(
    processed_company_dir: Path,
    provenance: dict[str, ReportProvenance],
) -> None:
    for report_type, prov in provenance.items():
        report_dir = processed_company_dir / report_type
        if not report_dir.exists():
            continue
        path = report_dir / "metadata.json"
        data = load_json(path, {})
        data.update(prov.to_metadata())
        data["metadata_version"] = METADATA_VERSION
        save_json(path, data)

    processed_meta_path = processed_company_dir / "processed_metadata.json"
    processed_meta = load_json(processed_meta_path, {})
    reports = processed_meta.setdefault("reports", {})
    for report_type, prov in provenance.items():
        existing = reports.get(report_type)
        if existing is None:
            existing = {}
        existing.update(prov.to_metadata())
        existing["metadata_version"] = METADATA_VERSION
        reports[report_type] = existing
    save_json(processed_meta_path, processed_meta)


def make_provenance_payload(
    prov: ReportProvenance,
    section: str | None,
    page: int | None,
) -> dict[str, Any]:
    payload = prov.to_metadata()
    payload.update(
        {
            "section": section,
            "page": page,
            "metadata_version": METADATA_VERSION,
        }
    )
    return payload


def enrich_business_profile_evidence(
    processed_company_dir: Path,
    provenance: dict[str, ReportProvenance],
    segments_by_report: dict[str, list[SectionSegment]],
) -> tuple[int, int]:
    path = processed_company_dir / "profile" / "profile_evidence.json"
    if not path.exists():
        return 0, 0

    data = load_json(path, {})
    business = data.get("categories", {}).get("business", {})
    evidence_list = business.get("evidence", [])

    updated = 0
    with_section = 0

    for evidence in evidence_list:
        report_type = evidence.get("report_type")
        prov = provenance.get(report_type)
        if not prov:
            continue

        section, page = locate_section(
            evidence.get("content") or evidence.get("markdown") or "",
            segments_by_report.get(report_type, []),
        )

        evidence.update(make_provenance_payload(prov, section, page))
        updated += 1
        if section:
            with_section += 1

    business["metadata_version"] = METADATA_VERSION
    save_json(path, data)
    return updated, with_section


def enrich_business_rag_chunks(
    processed_company_dir: Path,
    provenance: dict[str, ReportProvenance],
    segments_by_report: dict[str, list[SectionSegment]],
) -> tuple[int, int]:
    path = processed_company_dir / "rag" / "rag_chunks.json"
    if not path.exists():
        return 0, 0

    data = load_json(path, {})
    chunks = data.get("chunks", [])

    updated = 0
    with_section = 0

    for chunk in chunks:
        if chunk.get("category") != "business":
            continue

        report_type = chunk.get("report_type")
        prov = provenance.get(report_type)
        if not prov:
            continue

        section, page = locate_section(
            chunk.get("content", ""),
            segments_by_report.get(report_type, []),
        )

        metadata = chunk.setdefault("metadata", {})
        metadata.update(make_provenance_payload(prov, section, page))

        # Retriever/Builder의 버전 차이를 고려해 provenance 핵심값은 chunk top-level에도 둔다.
        # 기존 consumer가 metadata를 보더라도, top-level을 보더라도 동일 값을 얻을 수 있다.
        chunk["report"] = prov.report_name or report_type
        chunk["rcept_no"] = prov.rcept_no
        chunk["filing_date"] = prov.filing_date
        chunk["period"] = prov.period
        chunk["period_start"] = prov.period_start
        chunk["period_end"] = prov.period_end
        chunk["period_type"] = prov.period_type
        chunk["section"] = section
        chunk["page"] = page

        updated += 1
        if section:
            with_section += 1

    data["business_metadata_version"] = METADATA_VERSION
    save_json(path, data)
    return updated, with_section


def validate_business_metadata(processed_company_dir: Path) -> dict[str, Any]:
    path = processed_company_dir / "rag" / "rag_chunks.json"
    if not path.exists():
        return {"business_chunks": 0}

    data = load_json(path, {})
    chunks = [c for c in data.get("chunks", []) if c.get("category") == "business"]

    required = ["rcept_no", "filing_date", "period", "section"]
    counts = {key: 0 for key in required + ["page"]}

    for chunk in chunks:
        md = chunk.get("metadata", {})
        for key in counts:
            if md.get(key) not in (None, "", []):
                counts[key] += 1

    total = len(chunks)
    return {
        "business_chunks": total,
        "filled": counts,
        "fill_rate": {
            key: round(value / total, 4) if total else 0.0
            for key, value in counts.items()
        },
        "required_complete": sum(
            1
            for chunk in chunks
            if all(
                chunk.get("metadata", {}).get(key) not in (None, "", [])
                for key in required
            )
        ),
        "page_note": "page는 안정적으로 매핑되는 경우만 채우며 null 허용",
    }


def enrich_business_metadata(
    project_root: Path,
    company: str,
    corp_code: str | None = None,
) -> dict[str, Any]:
    data_root = project_root / "data"
    raw_root = data_root / "raw" / "dart"
    processed_root = data_root / "processed"

    raw_company_dir = find_company_dir(raw_root, company, corp_code, "metadata.json")
    processed_company_dir = find_company_dir(
        processed_root, company, corp_code, "processed_metadata.json"
    )

    raw_metadata = load_json(raw_company_dir / "metadata.json", {})
    selected_reports = raw_metadata.get("selected_reports", {})

    provenance: dict[str, ReportProvenance] = {}
    segments_by_report: dict[str, list[SectionSegment]] = {}

    for report_type in REPORT_TYPES:
        report_dir = processed_company_dir / report_type
        if not report_dir.exists():
            continue

        prov = build_report_provenance(
            report_type=report_type,
            raw_selected=selected_reports,
            processed_report_dir=report_dir,
        )
        provenance[report_type] = prov

        document_md = read_text(report_dir / "document.md")
        segments_by_report[report_type] = build_section_segments(document_md)

    enrich_report_metadata(processed_company_dir, provenance)

    evidence_updated, evidence_with_section = enrich_business_profile_evidence(
        processed_company_dir,
        provenance,
        segments_by_report,
    )

    chunks_updated, chunks_with_section = enrich_business_rag_chunks(
        processed_company_dir,
        provenance,
        segments_by_report,
    )

    validation = validate_business_metadata(processed_company_dir)

    return {
        "company": company,
        "corp_code": corp_code,
        "raw_company_dir": str(raw_company_dir),
        "processed_company_dir": str(processed_company_dir),
        "metadata_version": METADATA_VERSION,
        "reports": {
            k: v.to_metadata()
            for k, v in provenance.items()
        },
        "profile_evidence": {
            "business_evidence_updated": evidence_updated,
            "section_resolved": evidence_with_section,
        },
        "rag_chunks": {
            "business_chunks_updated": chunks_updated,
            "section_resolved": chunks_with_section,
        },
        "validation": validation,
    }


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def default_project_root() -> Path:
    here = Path(__file__).resolve()
    # scripts/ 안에 두는 경우 repo root는 parents[1]
    if here.parent.name == "scripts":
        return here.parents[1]
    return Path.cwd()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PeerProof Business RAG provenance metadata 보강"
    )
    parser.add_argument("--company", required=True, help='예: "에이피알"')
    parser.add_argument("--corp-code", default=None, help='예: "01190568"')
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="PeerProof repository root. 생략하면 현재 project root 추정",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = (args.project_root or default_project_root()).resolve()

    print("=" * 72)
    print("PEERPROOF / BUSINESS METADATA ENRICHER")
    print("=" * 72)
    print(f"project_root : {project_root}")
    print(f"company      : {args.company}")
    print(f"corp_code    : {args.corp_code or '-'}")
    print()

    result = enrich_business_metadata(
        project_root=project_root,
        company=args.company,
        corp_code=args.corp_code,
    )

    print("[REPORT PROVENANCE]")
    for report_type, meta in result["reports"].items():
        print(
            f"- {report_type:<10} "
            f"rcept_no={meta.get('rcept_no')} "
            f"filing_date={meta.get('filing_date')} "
            f"period={meta.get('period')} "
            f"period_type={meta.get('period_type')}"
        )

    print()
    print("[BUSINESS EVIDENCE]")
    print(result["profile_evidence"])
    print()
    print("[BUSINESS RAG CHUNKS]")
    print(result["rag_chunks"])
    print()
    print("[VALIDATION]")
    print(json.dumps(result["validation"], ensure_ascii=False, indent=2))
    print()
    print("완료: Business metadata를 report/evidence/chunk에 반영했습니다.")
    print("page는 안정적으로 확인되는 경우만 채우며 null을 허용합니다.")


if __name__ == "__main__":
    main()
