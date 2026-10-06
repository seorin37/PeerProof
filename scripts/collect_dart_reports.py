"""Run from PeerProof: python scripts/collect_dart_reports.py --company 에이피알"""
import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from peerproof.dart.client import DartClient, DartError
from peerproof.dart.filings import REPORT_TYPES, collect_filings, resolve_company


def main():
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    try:
        start = today.replace(year=today.year - 3)
    except ValueError:
        start = today.replace(year=today.year - 3, day=28)
    parser = argparse.ArgumentParser(description="DART 사업·반기·분기보고서 원문 수집")
    parser.add_argument("--company", required=True, help="기업명, 영문명, 6자리 종목코드 또는 8자리 DART 고유번호")
    parser.add_argument("--start-date", default=start.strftime("%Y%m%d"))
    parser.add_argument("--end-date", default=today.strftime("%Y%m%d"))
    parser.add_argument("--report-types", nargs="+", choices=REPORT_TYPES, default=list(REPORT_TYPES))
    parser.add_argument("--include-corrections", action="store_true", help="정정을 포함한 모든 제출본 조회")
    parser.add_argument("--refresh-companies", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/raw/dart")
    args = parser.parse_args()
    client = None
    try:
        for value in (args.start_date, args.end_date):
            datetime.strptime(value, "%Y%m%d")
        if args.start_date > args.end_date:
            raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")
        client = DartClient()
        company = resolve_company(client, args.company, args.output_dir / "_cache", args.refresh_companies)
        print(f"기업: {company['corp_name']} ({company['corp_code']})", flush=True)
        manifest, filings, failures = collect_filings(
            client, company, args.start_date, args.end_date, args.output_dir,
            args.report_types, not args.include_corrections
        )
        print(f"수집 결과: {len(filings)}건 중 {len(filings) - len(failures)}건 성공")
        print(f"목록: {manifest}")
        return 1 if failures else 0
    except (DartError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
