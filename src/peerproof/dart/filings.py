"""Company resolution and reusable periodic-report collection."""
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from .client import DartError

REPORT_TYPES = {"annual": "A001", "semiannual": "A002", "quarterly": "A003"}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def save_archive(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".zip.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def resolve_company(client, query, cache_dir, refresh=False):
    cache = Path(cache_dir) / "corp_codes.zip"
    if refresh or not cache.exists():
        save_archive(cache, client.archive("corpCode.xml"))
    with zipfile.ZipFile(cache) as archive:
        candidates = [name for name in archive.namelist() if name.lower().endswith(".xml")]
        if len(candidates) != 1:
            raise DartError("기업 고유번호 파일 형식이 예상과 다릅니다.")
        root = ET.fromstring(archive.read(candidates[0]))
    companies = [
        {child.tag: (child.text or "").strip() for child in node}
        for node in root.findall("list")
    ]
    normalized = query.strip().casefold()
    exact = [company for company in companies if normalized in {
        company.get("corp_code", "").casefold(),
        company.get("stock_code", "").casefold(),
        company.get("corp_name", "").casefold(),
        company.get("corp_eng_name", "").casefold(),
    }]
    if not exact:
        exact = [company for company in companies
                 if normalized in company.get("corp_name", "").casefold()
                 or normalized in company.get("corp_eng_name", "").casefold()]
    if len(exact) != 1:
        names = ", ".join(f"{c['corp_name']} ({c['corp_code']})" for c in exact[:10])
        raise DartError(f"기업을 하나로 식별할 수 없습니다: {names or '검색 결과 없음'}. 종목코드 또는 고유번호를 사용하세요.")
    return exact[0]


def list_periodic_filings(client, corp_code, start_date, end_date,
                         report_types=tuple(REPORT_TYPES), final_only=True):
    for value in (start_date, end_date):
        datetime.strptime(value, "%Y%m%d")
    if start_date > end_date:
        raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")
    if not re.fullmatch(r"\d{8}", corp_code):
        raise ValueError("DART 고유번호는 8자리 숫자여야 합니다.")
    rows = {}
    for report_type in report_types:
        detail = REPORT_TYPES[report_type]
        page = 1
        while True:
            data = client.json(
                "list.json", corp_code=corp_code, bgn_de=start_date, end_de=end_date,
                pblntf_detail_ty=detail, last_reprt_at="Y" if final_only else "N",
                page_no=page, page_count=100, sort="date", sort_mth="asc"
            )
            if data["status"] == "013":
                break
            for item in data.get("list", []):
                period = re.search(r"\((\d{4}\.\d{2})\)", item["report_nm"])
                rows[item["rcept_no"]] = {
                    **item, "report_type": report_type,
                    "report_period": period.group(1) if period else None,
                    "source_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item['rcept_no']}",
                }
            if page >= int(data.get("total_page", 1)):
                break
            page += 1
    return sorted(rows.values(), key=lambda row: (row["rcept_dt"], row["rcept_no"]))


def collect_filings(client, company, start_date, end_date, output_dir,
                    report_types=tuple(REPORT_TYPES), final_only=True):
    directory = Path(output_dir) / company["corp_code"]
    directory.mkdir(parents=True, exist_ok=True)
    filings = list_periodic_filings(
        client, company["corp_code"], start_date, end_date, report_types, final_only
    )
    manifest = {
        "company": company,
        "query": {"start_date": start_date, "end_date": end_date,
                  "date_basis": "filing_receipt_date", "report_types": list(report_types),
                  "final_only": final_only},
        "filings": filings,
    }
    manifest_path = directory / f"manifest_{start_date}_{end_date}.json"
    write_json(manifest_path, manifest)
    failures = []
    for filing in filings:
        receipt = filing["rcept_no"]
        if not re.fullmatch(r"\d{14}", receipt):
            raise DartError("잘못된 공시 접수번호")
        report_dir = directory / receipt
        report_dir.mkdir(exist_ok=True)
        archive_path = report_dir / "document.zip"
        try:
            valid_cache = False
            if archive_path.exists() and zipfile.is_zipfile(archive_path):
                with zipfile.ZipFile(archive_path) as archive:
                    valid_cache = archive.testzip() is None
            if not valid_cache:
                save_archive(archive_path, client.archive("document.xml", rcept_no=receipt))
            with zipfile.ZipFile(archive_path) as archive:
                filing["document_files"] = archive.namelist()
            filing["archive_path"] = str(archive_path.relative_to(directory))
            filing["download_status"] = "ok"
            print(f"[OK] {filing['report_nm']} ({receipt})", flush=True)
        except DartError as error:
            filing["download_status"] = "failed"
            filing["error"] = str(error)
            failures.append(receipt)
            print(f"[FAIL] {filing['report_nm']} ({receipt}): {error}", flush=True)
        write_json(report_dir / "metadata.json", filing)
        write_json(manifest_path, manifest)
    return manifest_path, filings, failures
