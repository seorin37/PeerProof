import copy
import unittest

from peerproof.finance.finance_latest import (
    extract_report,
    select_latest,
    parse_amount,
)


def row(
    account_id,
    statement,
    amount,
    cumulative=None,
    name="",
    year="2023",
    code="11014",
    receipt="20231114001221",
):
    result = {
        "corp_code": "01190568",
        "bsns_year": year,
        "reprt_code": code,
        "rcept_no": receipt,
        "sj_div": statement,
        "sj_nm": statement,
        "account_id": account_id,
        "account_nm": name,
        "currency": "KRW",
        "thstrm_amount": amount,
    }

    if cumulative is not None:
        result["thstrm_add_amount"] = cumulative

    return result


def payload(rows, scope="CFS"):
    return {
        "fs_div": scope,
        "statements": rows,
    }


class ExtractionTests(unittest.TestCase):
    def test_interim_requires_ytd_not_quarter(self):
        r = row(
            "ifrs-full_Revenue",
            "CIS",
            "30",
            "90",
        )

        self.assertEqual(
            extract_report(payload([r]))["accounts"]["revenue"]["value"],
            90,
        )

        del r["thstrm_add_amount"]

        self.assertIsNone(
            extract_report(payload([r]))["accounts"]["revenue"]["value"]
        )

    def test_total_and_parent_are_distinct(self):
        rows = [
            row(
                "ifrs-full_ProfitLoss",
                "CIS",
                "20",
                "100",
            ),
            row(
                "ifrs-full_ProfitLossAttributableToOwnersOfParent",
                "CIS",
                "15",
                "80",
            ),
        ]

        a = extract_report(payload(rows))["accounts"]

        self.assertEqual(
            a["net_income_total"]["value"],
            100,
        )

        self.assertEqual(
            a["net_income_parent"]["value"],
            80,
        )

    def test_cfs_missing_parent_stays_missing(self):
        a = extract_report(
            payload(
                [
                    row(
                        "ifrs-full_ProfitLoss",
                        "CIS",
                        "20",
                        "100",
                    )
                ]
            )
        )["accounts"]

        self.assertEqual(
            a["net_income_parent"]["status"],
            "missing",
        )

    def test_ofs_parent_mapping_has_provenance(self):
        a = extract_report(
            payload(
                [
                    row(
                        "ifrs-full_ProfitLoss",
                        "CIS",
                        "20",
                        "100",
                    )
                ],
                "OFS",
            )
        )["accounts"]

        self.assertEqual(
            a["net_income_parent"]["value"],
            100,
        )

        self.assertEqual(
            a["net_income_parent"]["match_method"],
            "standalone_mapping",
        )

    def test_balance_does_not_use_cumulative(self):
        a = extract_report(
            payload(
                [
                    row(
                        "ifrs-full_Assets",
                        "BS",
                        "200",
                        "999",
                    )
                ]
            )
        )["accounts"]

        self.assertEqual(
            a["total_assets"]["value"],
            200,
        )

        self.assertIsNone(
            a["total_assets"]["period_start"]
        )

    def test_cash_flow_uses_reported_ytd_current_field(self):
        a = extract_report(
            payload(
                [
                    row(
                        "ifrs-full_CashFlowsFromUsedInOperatingActivities",
                        "CF",
                        "-60",
                    )
                ]
            )
        )["accounts"]

        self.assertEqual(
            a["operating_cash_flow"]["value"],
            -60,
        )

    def test_ignore_profit_in_cf_and_sce(self):
        a = extract_report(
            payload(
                [
                    row(
                        "ifrs-full_ProfitLoss",
                        "CF",
                        "500",
                    )
                ]
            )
        )["accounts"]

        self.assertIsNone(
            a["net_income_total"]["value"]
        )

    def test_conflicting_equal_priority_rows(self):
        rows = [
            row(
                "ifrs-full_Revenue",
                "CIS",
                "20",
                "100",
            ),
            row(
                "ifrs-full_Revenue",
                "IS",
                "20",
                "101",
            ),
        ]

        self.assertEqual(
            extract_report(payload(rows))["accounts"]["revenue"]["status"],
            "ambiguous",
        )

    def test_no_partial_revenue_matching(self):
        a = extract_report(
            payload(
                [
                    row(
                        "custom",
                        "CIS",
                        "20",
                        "100",
                        "이자수익",
                    )
                ]
            )
        )["accounts"]

        self.assertIsNone(
            a["revenue"]["value"]
        )

    def test_large_negative_zero_and_missing(self):
        self.assertEqual(
            parse_amount("9007199254740993"),
            9007199254740993,
        )

        self.assertEqual(
            parse_amount("(1,234)"),
            -1234,
        )

        self.assertEqual(
            parse_amount("0"),
            0,
        )

        self.assertIsNone(
            parse_amount("-")
        )

        with self.assertRaises(ValueError):
            parse_amount(1.0)

    def test_source_receipt_mismatch_rejected(self):
        p = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                )
            ]
        )

        p["source_report"] = {
            "rcept_no": "20231114009999"
        }

        with self.assertRaises(ValueError):
            extract_report(p)

    def test_asof_cutoff(self):
        p = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                )
            ]
        )

        with self.assertRaises(ValueError):
            extract_report(
                p,
                as_of="2023-11-13",
            )

        self.assertEqual(
            extract_report(
                p,
                as_of="2023-11-14",
            )["context"]["period_end"],
            "2023-09-30",
        )

    def test_annual_after_q3_same_year(self):
        q = extract_report(
            payload(
                [
                    row(
                        "ifrs-full_Assets",
                        "BS",
                        "200",
                    )
                ]
            )
        )

        fy = extract_report(
            payload(
                [
                    row(
                        "ifrs-full_Assets",
                        "BS",
                        "300",
                        year="2023",
                        code="11011",
                        receipt="20240321000964",
                    )
                ]
            )
        )

        self.assertEqual(
            select_latest([q, fy])["context"]["period_type"],
            "FY",
        )

    def test_scope_preference_only_at_same_endpoint(self):
        rows = [
            row(
                "ifrs-full_Assets",
                "BS",
                "200",
            )
        ]

        cfs = extract_report(
            payload(rows, "CFS")
        )

        ofs = extract_report(
            payload(rows, "OFS")
        )

        self.assertEqual(
            select_latest([ofs, cfs])["context"]["fs_div"],
            "CFS",
        )

        newer = extract_report(
            payload(
                [
                    row(
                        "ifrs-full_Assets",
                        "BS",
                        "300",
                        year="2023",
                        code="11011",
                        receipt="20240321000964",
                    )
                ],
                "OFS",
            )
        )

        self.assertEqual(
            select_latest([cfs, newer])["context"]["fs_div"],
            "OFS",
        )

    def test_non_december_needs_explicit_dates(self):
        p = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                )
            ]
        )

        p["fiscal_year_end_month"] = 3

        with self.assertRaises(ValueError):
            extract_report(p)

        p.update(
            period_start="2022-04-01",
            period_end="2022-12-31",
        )

        self.assertEqual(
            extract_report(p)["context"]["period_date_basis"],
            "provided_dates",
        )


class V2Tests(unittest.TestCase):
    def test_q1_falls_back_to_quarter_amount(self):
        r = row(
            "ifrs-full_Revenue",
            "CIS",
            "30",
            "",
            code="11013",
            receipt="20230515001164",
        )

        a = extract_report(
            payload([r])
        )["accounts"]["revenue"]

        self.assertEqual(
            (
                a["value"],
                a["amount_field"],
            ),
            (
                30,
                "thstrm_amount",
            ),
        )

    def test_h1_never_falls_back_to_quarter_amount(self):
        r = row(
            "ifrs-full_Revenue",
            "CIS",
            "30",
            "",
            code="11012",
            receipt="20230814002584",
        )

        self.assertEqual(
            extract_report(
                payload([r])
            )["accounts"]["revenue"]["status"],
            "missing",
        )

    def test_opening_equity_from_same_report(self):
        r = row(
            "ifrs-full_EquityAttributableToOwnersOfParent",
            "BS",
            "168",
        )

        r["frmtrm_amount"] = "99"
        r["frmtrm_nm"] = "제 9 기말"

        a = extract_report(
            payload([r])
        )["accounts"]

        self.assertEqual(
            a["equity_parent"]["value"],
            168,
        )

        self.assertEqual(
            a["equity_parent_begin"]["value"],
            99,
        )

        self.assertEqual(
            a["equity_parent_begin"]["period_end"],
            "2022-12-31",
        )

        self.assertEqual(
            a["equity_parent_begin"]["amount_field"],
            "frmtrm_amount",
        )

    def test_ofs_opening_equity_mapping(self):
        r = row(
            "ifrs-full_Equity",
            "BS",
            "45",
        )

        r["frmtrm_amount"] = "33"

        a = extract_report(
            payload(
                [r],
                "OFS",
            )
        )["accounts"]

        self.assertEqual(
            a["equity_parent_begin"]["value"],
            33,
        )

        self.assertEqual(
            a["equity_parent_begin"]["match_method"],
            "standalone_mapping",
        )

    def test_name_fallback_excludes_tagged_comprehensive(self):
        ni = row(
            "custom",
            "CIS",
            "18",
            "57",
            name="지배기업 소유주지분",
        )

        ci = row(
            "ifrs-full_ComprehensiveIncomeAttributableToOwnersOfParent",
            "CIS",
            "19",
            "58",
            name="지배기업 소유주지분",
        )

        a = extract_report(
            payload([ci, ni])
        )["accounts"]["net_income_parent"]

        self.assertEqual(
            a["value"],
            57,
        )

    def test_name_fallback_untagged_duplicates_stay_ambiguous(self):
        # Real APR Q3 file lists comprehensive rows BEFORE profit rows
        # (ord 13 vs 31), so no order-based guess is allowed.

        ci = row(
            "custom",
            "CIS",
            "19",
            "58",
            name="지배기업 소유주지분",
        )
        ci["ord"] = "13"

        ni = row(
            "custom",
            "CIS",
            "18",
            "57",
            name="지배기업 소유주지분",
        )
        ni["ord"] = "31"

        a = extract_report(
            payload([ci, ni])
        )["accounts"]["net_income_parent"]

        self.assertEqual(
            a["status"],
            "ambiguous",
        )

    def test_same_day_identical_values_not_conflict(self):
        p1 = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                )
            ]
        )

        p2 = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                    receipt="20231114009999",
                )
            ]
        )

        chosen = select_latest(
            [
                extract_report(
                    p1,
                    "a",
                ),
                extract_report(
                    p2,
                    "b",
                ),
            ]
        )

        self.assertEqual(
            chosen["accounts"]["total_assets"]["value"],
            200,
        )

    def test_cli_requires_as_of(self):
        import subprocess
        import sys

        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "peerproof.finance.finance_latest",
                "x.json",
                "--output",
                "o.json",
            ],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(
            r.returncode,
            0,
        )

        self.assertIn(
            "--as-of",
            r.stderr,
        )


class V3ReviewTests(unittest.TestCase):
    def test_duplicate_currency_conflict(self):
        p1 = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                )
            ]
        )

        p2 = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                    receipt="20231114009999",
                )
            ]
        )

        p2["statements"][0]["currency"] = "USD"

        with self.assertRaises(ValueError):
            select_latest(
                [
                    extract_report(p1),
                    extract_report(p2),
                ]
            )

    def test_duplicate_start_date_conflict(self):
        p1 = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                )
            ]
        )

        p2 = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                    receipt="20231114009999",
                )
            ]
        )

        p2.update(
            period_start="2023-04-01",
            period_end="2023-09-30",
        )

        with self.assertRaises(ValueError):
            select_latest(
                [
                    extract_report(p1),
                    extract_report(p2),
                ]
            )

    def test_q1_invalid_cumulative_is_not_missing(self):
        p = payload(
            [
                row(
                    "ifrs-full_Revenue",
                    "CIS",
                    "30",
                    "bad",
                    code="11013",
                    receipt="20230515001164",
                )
            ]
        )

        a = extract_report(
            p
        )["accounts"]["revenue"]

        self.assertEqual(
            a["status"],
            "invalid",
        )

        self.assertIsNone(
            a["value"]
        )

    def test_string_december_month(self):
        p = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                )
            ]
        )

        p["fiscal_year_end_month"] = "12"

        self.assertEqual(
            extract_report(p)["context"]["period_end"],
            "2023-09-30",
        )

    def test_string_nondecember_month_rejected(self):
        p = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                )
            ]
        )

        p["fiscal_year_end_month"] = "03"

        with self.assertRaises(ValueError):
            extract_report(p)

    def test_inconsistent_filing_date_cannot_bypass_cutoff(self):
        p = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                    code="11011",
                    receipt="20240321000964",
                )
            ]
        )

        p["source_report"] = {
            "rcept_date": "20240101"
        }

        with self.assertRaises(ValueError):
            extract_report(
                p,
                as_of="2024-02-13",
            )

    def test_compatible_duplicate_sources_and_order_independence(self):
        p1 = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                )
            ]
        )

        p2 = payload(
            [
                row(
                    "ifrs-full_Assets",
                    "BS",
                    "200",
                    receipt="20231114009999",
                )
            ]
        )

        reports = [
            extract_report(
                p1,
                "a",
            ),
            extract_report(
                p2,
                "b",
            ),
        ]

        forward = select_latest(
            reports
        )

        reverse = select_latest(
            list(
                reversed(
                    reports
                )
            )
        )

        self.assertEqual(
            forward,
            reverse,
        )

        self.assertEqual(
            len(
                forward["compatible_duplicate_sources"]
            ),
            2,
        )


class APRGoldenTest(unittest.TestCase):
    """
    실데이터 정답 검증.

    PEERPROOF_DATA=data.zip
    또는
    PEERPROOF_DATA=data/processed/에이피알/finance/raw

    형태로 지정하면 실행된다.
    """

    EXPECTED = {
        "revenue": 371789961905,
        "operating_income": 69834074349,
        "net_income_parent": 57440565991,
        "net_income_total": 57440565991,
        "total_assets": 248039138389,
        "total_liabilities": 79364238582,
        "total_equity": 168674899807,
        "equity_parent": 168674899807,
        "operating_cash_flow": 60836797402,
        "ppe_purchase_cash": 6682419461,
        "intangible_purchase_cash": 1473573071,
        "equity_parent_begin": 99266311538,
        "total_equity_begin": 99266311538,
    }

    def test_apr_2023q3(self):
        import os
        from pathlib import Path

        from peerproof.finance.finance_latest import read_payloads

        path = os.environ.get(
            "PEERPROOF_DATA"
        )

        if not path:
            self.skipTest(
                "PEERPROOF_DATA 미지정"
            )

        reports = [
            extract_report(
                p,
                n,
                as_of="2023-12-21",
            )
            for n, p in read_payloads(
                Path(path)
            )
        ]

        chosen = select_latest(
            reports
        )

        self.assertEqual(
            chosen["context"]["rcept_no"],
            "20231114001221",
        )

        self.assertEqual(
            chosen["context"]["period_type"],
            "Q3_YTD",
        )

        for key, expected in self.EXPECTED.items():
            self.assertEqual(
                chosen["accounts"][key]["value"],
                expected,
                key,
            )

            self.assertEqual(
                chosen["accounts"][key]["status"],
                "found",
                key,
            )


if __name__ == "__main__":
    unittest.main()