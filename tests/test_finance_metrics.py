"""합성 기업 정상/경계 사례 + APR 제공 출력 + 선택적 APR 원본 통합 테스트."""
import copy
from decimal import Decimal, Inexact, ROUND_DOWN, localcontext
from fractions import Fraction
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from peerproof.finance.finance_latest import extract_report, read_payloads, select_latest
from peerproof.finance.finance_metrics import calculate_company, calculate_document, METRICS
from peerproof.finance.integration_example import build_finance_payload, ui_text

HERE = Path(__file__).resolve().parent


def synthetic_company(scope="CFS", code="11014", currency="KRW", corp="00000001"):
    """실제 기업 데이터가 아닌, 알려진 정답을 갖는 API 모양의 합성 기업."""
    amount = {"revenue": 1000, "operating_income": 200, "net_income_total": 100,
              "net_income_parent": 80, "total_assets": 900, "total_liabilities": 300,
              "total_equity": 600, "equity_parent": 400, "operating_cash_flow": 150,
              "ppe_purchase_cash": 30, "intangible_purchase_cash": 10}
    ids = {"revenue": ("ifrs-full_Revenue", "CIS"),
           "operating_income": ("dart_OperatingIncomeLoss", "CIS"),
           "net_income_total": ("ifrs-full_ProfitLoss", "CIS"),
           "net_income_parent": ("ifrs-full_ProfitLossAttributableToOwnersOfParent", "CIS"),
           "total_assets": ("ifrs-full_Assets", "BS"),
           "total_liabilities": ("ifrs-full_Liabilities", "BS"),
           "total_equity": ("ifrs-full_Equity", "BS"),
           "equity_parent": ("ifrs-full_EquityAttributableToOwnersOfParent", "BS"),
           "operating_cash_flow": ("ifrs-full_CashFlowsFromUsedInOperatingActivities", "CF"),
           "ppe_purchase_cash": ("ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", "CF"),
           "intangible_purchase_cash": ("ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities", "CF")}
    receipt = {"11011": "20240321000964", "11013": "20230515001164",
               "11012": "20230814002584", "11014": "20231114001221"}[code]
    rows = []
    for key, value in amount.items():
        if scope == "OFS" and key in {"equity_parent", "net_income_parent"}:
            continue
        account_id, statement = ids[key]
        row = {"corp_code": corp, "bsns_year": "2023", "reprt_code": code,
               "rcept_no": receipt, "sj_div": statement, "account_id": account_id,
               "account_nm": key, "currency": currency, "thstrm_amount": str(value),
               "thstrm_add_amount": str(value)}
        if key in {"total_equity", "equity_parent"}:
            row["frmtrm_amount"] = "400"
        rows.append(row)
    return select_latest([extract_report({"fs_div": scope, "statements": rows}, as_of="2024-04-01")])


def add_synthetic_zero_confirmation(company, key, clear_raw=True):
    """테스트 전용 가짜 확인 기록. 실제 공시를 확인했다고 주장하는 자료가 아님."""
    ctx=company['context']
    if clear_raw:
        company['accounts'][key].update(value=None, raw_amount=None)
    proof={k:ctx[k] for k in ['corp_code','rcept_no','fs_div','period_start','period_end','source_url']}
    proof.update(verified=True, conclusion='no_cash_outflow', currency='KRW',
                 source_locator='합성 테스트 현금흐름표 취득 현금 당기 열',
                 note='합성 테스트에서 무지출이 확인된 상황을 모사')
    company.setdefault('zero_cashflow_confirmations',{})[key]=proof
    return proof


def metrics(company=None):
    return calculate_company(company or synthetic_company())["metrics"]


class FormulaTests(unittest.TestCase):
    def test_known_answers_for_all_nine_metrics(self):
        expected = {"cash_capex": "40", "operating_margin": "20", "net_margin": "10",
                    "roe": "20", "debt_ratio": "50", "simple_fcf": "110",
                    "cash_conversion": "150", "cfo_margin": "15", "capex_to_revenue": "4"}
        result = metrics()
        self.assertEqual(set(result), set(expected))
        for key, answer in expected.items():
            with self.subTest(key=key):
                self.assertEqual(result[key]["status"], "computed")
                self.assertEqual(Decimal(result[key]["value"]), Decimal(answer))

    def test_total_and_parent_not_interchangeable(self):
        c = synthetic_company(); c['accounts']['net_income_parent']['value'] = 40
        out = metrics(c)
        self.assertEqual(Decimal(out['net_margin']['value']), 10)
        self.assertEqual(Decimal(out['cash_conversion']['value']), 150)
        self.assertEqual(Decimal(out['roe']['value']), 10)

    def test_ofs_mapping_through_extractor(self):
        c = synthetic_company(scope="OFS"); out = metrics(c)
        self.assertEqual(c['accounts']['net_income_parent']['mapped_from'], 'net_income_total')
        self.assertEqual(c['accounts']['equity_parent_begin']['mapped_from'], 'total_equity_begin')
        self.assertEqual(Decimal(out['roe']['value']), 20)
        self.assertEqual(out['roe']['fs_div'], 'OFS')

    def test_four_report_types(self):
        for code, label in [('11011', '연간'), ('11013', '3개월 누적'), ('11012', '반기 누적'), ('11014', '9개월 누적')]:
            with self.subTest(code=code):
                out = metrics(synthetic_company(code=code))
                self.assertTrue(all(m['status']=='computed' for m in out.values()))
                self.assertIn(label, out['roe']['name'])
                self.assertFalse(out['roe']['annualized'])

    def test_capex_all_sign_combinations(self):
        for ppe in [30, -30]:
            for intangible in [10, -10]:
                c = synthetic_company()
                c['accounts']['ppe_purchase_cash']['value'] = ppe
                c['accounts']['intangible_purchase_cash']['value'] = intangible
                out = metrics(c)
                self.assertEqual(Decimal(out['cash_capex']['value']), 40)
                self.assertEqual(Decimal(out['simple_fcf']['value']), 110)

    def test_explicit_zero_capex(self):
        c = synthetic_company()
        for k in ['ppe_purchase_cash','intangible_purchase_cash']: c['accounts'][k]['value'] = 0
        out = metrics(c)
        self.assertEqual(Decimal(out['cash_capex']['value']), 0)
        self.assertEqual(Decimal(out['simple_fcf']['value']), 150)

    def test_negative_profits_and_cfo_preserved(self):
        c = synthetic_company()
        for k in ['operating_income','net_income_total','net_income_parent','operating_cash_flow']: c['accounts'][k]['value'] *= -1
        out = metrics(c)
        for k in ['operating_margin','net_margin','roe','simple_fcf','cfo_margin']:
            self.assertEqual(out[k]['status'], 'computed'); self.assertLess(Decimal(out[k]['value']), 0)
        self.assertEqual(out['cash_conversion']['status'], 'not_meaningful')

    def test_positive_profit_negative_cfo(self):
        c = synthetic_company(); c['accounts']['operating_cash_flow']['value'] = -150
        self.assertEqual(Decimal(metrics(c)['cash_conversion']['value']), -150)

    def test_zero_liabilities_is_valid(self):
        c = synthetic_company(); c['accounts']['total_liabilities']['value'] = 0
        self.assertEqual(metrics(c)['debt_ratio']['status'], 'computed')
        self.assertEqual(Decimal(metrics(c)['debt_ratio']['value']), 0)

    def test_uniform_thousand_units(self):
        c = synthetic_company()
        for a in c['accounts'].values(): a['unit_multiplier'] = 1000
        out = metrics(c)
        self.assertEqual(Decimal(out['cash_capex']['value']), 40000)
        self.assertEqual(Decimal(out['simple_fcf']['value']), 110000)
        self.assertEqual(Decimal(out['roe']['value']), 20)
        self.assertEqual(out['cash_capex']['unit_multiplier'], 1)

    def test_usd_company(self):
        out = metrics(synthetic_company(currency="USD"))
        self.assertEqual(out['simple_fcf']['unit'], 'USD')
        self.assertEqual(Decimal(out['simple_fcf']['value']), 110)

    def test_large_money_exact(self):
        c = synthetic_company()
        c['accounts']['ppe_purchase_cash']['value'] = 10**100 + 9007199254740993
        c['accounts']['intangible_purchase_cash']['value'] = 1
        expected = 10**100 + 9007199254740994
        self.assertEqual(Decimal(metrics(c)['cash_capex']['value']), expected)

    def test_decimal_money_and_display_rounding(self):
        c = synthetic_company(); c['accounts']['ppe_purchase_cash']['value'] = '30.005'
        out = metrics(c)
        self.assertEqual(Decimal(out['cash_capex']['value']), Decimal('40.005'))
        self.assertEqual(out['cash_capex']['display_value'], '40.01')

    def test_round_only_display_preserve_small_negative(self):
        c=synthetic_company(); c['accounts']['operating_income']['value']='-0.001'
        r=metrics(c)['operating_margin']
        self.assertLess(Decimal(r['value']), 0); self.assertEqual(r['display_value'], '0.00')

    def test_input_not_mutated_and_evidence_independent(self):
        c = synthetic_company(); before = copy.deepcopy(c)
        out = calculate_company(c)
        self.assertEqual(c, before)
        self.assertEqual(out['metrics']['roe']['source_inputs']['net_income_parent'], c['accounts']['net_income_parent'])
        out['metrics']['roe']['source_inputs']['net_income_parent']['value'] = 1
        self.assertEqual(c, before)

    def test_decimal_context_does_not_change_answers(self):
        with localcontext() as ctx:
            ctx.prec = 6; actual = metrics()
        self.assertEqual(actual, metrics())

    def test_all_report_scope_currency_combinations(self):
        for scope in ['CFS', 'OFS']:
            for code in ['11011', '11013', '11012', '11014']:
                for currency in ['KRW', 'USD', 'AUD']:
                    with self.subTest(scope=scope, code=code, currency=currency):
                        out = metrics(synthetic_company(scope=scope, code=code, currency=currency))
                        self.assertTrue(all(m['status']=='computed' for m in out.values()))
                        self.assertEqual(Decimal(out['cash_capex']['value']), 40)

    def test_caller_decimal_rounding_and_traps_do_not_change_result(self):
        c=synthetic_company(); c['accounts']['revenue']['value']=3000
        expected=metrics(c)
        with localcontext() as ctx:
            ctx.prec=6; ctx.rounding=ROUND_DOWN; ctx.traps[Inexact]=True
            actual=metrics(c)
        self.assertEqual(actual, expected)

    def test_random_integer_formulas_against_fraction(self):
        rng = random.Random(20261007)
        for _ in range(100):
            revenue, op, total, parent, eq0, eq1, liabilities, cfo, ppe, intangible = [rng.randint(1,10**12) for _ in range(10)]
            keys=['revenue','operating_income','net_income_total','net_income_parent','equity_parent_begin','equity_parent','total_liabilities','operating_cash_flow','ppe_purchase_cash','intangible_purchase_cash']
            nums=[revenue,op,total,parent,eq0,eq1,liabilities,cfo,ppe,intangible]
            c=synthetic_company()
            for key,num in zip(keys,nums): c['accounts'][key]['value']=num
            c['accounts']['total_equity']['value']=eq1
            out=metrics(c)
            expected={'cash_capex':Fraction(ppe+intangible),'simple_fcf':Fraction(cfo-ppe-intangible),
                      'operating_margin':Fraction(op*100,revenue),'net_margin':Fraction(total*100,revenue),
                      'roe':Fraction(parent*200,eq0+eq1),'debt_ratio':Fraction(liabilities*100,eq1),
                      'cash_conversion':Fraction(cfo*100,total),'cfo_margin':Fraction(cfo*100,revenue),
                      'capex_to_revenue':Fraction((ppe+intangible)*100,revenue)}
            with localcontext() as ctx:
                ctx.prec=80
                for key,f in expected.items():
                    target=Decimal(f.numerator)/Decimal(f.denominator)
                    error=abs(Decimal(out[key]['value'])-target)
                    self.assertLessEqual(error, max(abs(target),Decimal(1))*Decimal('1e-38'))


class ValidationTests(unittest.TestCase):
    def test_each_required_input_missing_only_blocks_its_dependents(self):
        for missing_key in {k for d in METRICS.values() for k in d[2]}:
            c=synthetic_company(); c['accounts'].pop(missing_key); out=metrics(c)
            for key,definition in METRICS.items(): self.assertEqual(out[key]['status'], 'missing' if missing_key in definition[2] else 'computed')

    def test_invalid_and_ambiguous_each_input(self):
        for bad_key in {k for d in METRICS.values() for k in d[2]}:
            for state in ['ambiguous','invalid','unrecognized']:
                c=synthetic_company(); c['accounts'][bad_key].update(status=state,value=None,reason='합성 오류'); out=metrics(c)
                for key,definition in METRICS.items(): self.assertEqual(out[key]['status'], 'review_required' if bad_key in definition[2] else 'computed')

    def test_missing_status_never_uses_stale_value(self):
        c=synthetic_company(); c['accounts']['ppe_purchase_cash']['status']='missing'
        r=metrics(c)['cash_capex']
        self.assertEqual(r['status'],'missing'); self.assertIsNone(r['value']); self.assertFalse(r['assumptions'])

    def test_review_error_priority_over_missing(self):
        c=synthetic_company(); c['accounts'].pop('ppe_purchase_cash'); c['accounts']['intangible_purchase_cash']['status']='ambiguous'
        r=metrics(c)['cash_capex']; self.assertEqual(r['status'],'review_required'); self.assertEqual(len(r['reasons']),2)

    def test_invalid_numeric_inputs(self):
        for value in [None,1.0,True,False,'NaN','Infinity','-Infinity','bad','1,000','1e3',{},[], '9'*129]:
            c=synthetic_company(); c['accounts']['revenue']['value']=value; r=metrics(c)['operating_margin']
            self.assertEqual(r['status'],'review_required',repr(value)); self.assertIsNone(r['value'])

    def test_nonfinite_python_values_rejected_as_bad_json(self):
        for value in [float('nan'), float('inf'), Decimal('10')]:
            c=synthetic_company(); c['accounts']['revenue']['value']=value
            with self.assertRaises(ValueError): calculate_company(c)

    def test_bad_statement_div_type_returns_review(self):
        c=synthetic_company(); c['accounts']['revenue']['statement_div']=[]
        self.assertEqual(metrics(c)['operating_margin']['status'], 'review_required')
        out=calculate_document({'companies':{'00000001':c}})
        self.assertEqual(out['companies']['00000001']['metrics']['operating_margin']['status'], 'review_required')

    def test_source_metadata_mutation_matrix(self):
        c=synthetic_company()
        values=[None, {}, [], True, False, 0, 1, '', 'bad']
        fields=['value','status','currency','unit_multiplier','statement_div','amount_field',
                'period_start','period_end','fs_div','rcept_no','match_method','mapped_from']
        for field in fields:
            for value in values:
                x=copy.deepcopy(c); x['accounts']['revenue'][field]=value
                out=calculate_document({'companies':{'00000001':x}})
                json.dumps(out, allow_nan=False)
                # 제어되지 않은 TypeError/ZeroDivisionError 등이 없어야 함.

    def test_zero_negative_denominators(self):
        for value in [0,-1]:
            for key,affected in [('revenue',['operating_margin','net_margin','cfo_margin','capex_to_revenue']),
                                 ('net_income_total',['cash_conversion']),('total_equity',['debt_ratio']),
                                 ('equity_parent_begin',['roe']),('equity_parent',['roe'])]:
                c=synthetic_company(); c['accounts'][key]['value']=value
                for metric in affected: self.assertEqual(metrics(c)[metric]['status'],'not_meaningful')

    def test_negative_liabilities(self):
        c=synthetic_company(); c['accounts']['total_liabilities']['value']=-1
        self.assertEqual(metrics(c)['debt_ratio']['status'],'not_meaningful')

    def test_currency_mismatch_and_missing(self):
        for value in ['USD',None,'krw',{},123]:
            c=synthetic_company(); c['accounts']['ppe_purchase_cash']['currency']=value
            self.assertEqual(metrics(c)['cash_capex']['status'],'review_required')

    def test_unit_mismatch_and_invalid(self):
        for value in [1000,0,-1,'bad',None,1.0,'1.5','10000000000000']:
            c=synthetic_company(); c['accounts']['ppe_purchase_cash']['unit_multiplier']=value
            self.assertEqual(metrics(c)['cash_capex']['status'],'review_required')

    def test_period_scope_receipt_statement_and_field_mismatch(self):
        changes={'period_start':'2023-04-01','period_end':'2023-06-30','fs_div':'OFS',
                 'rcept_no':'20231114009999','statement_div':'BS','amount_field':'thstrm_amount'}
        for field,value in changes.items():
            c=synthetic_company(); c['accounts']['revenue'][field]=value
            self.assertEqual(metrics(c)['operating_margin']['status'],'review_required',field)

    def test_roe_requires_begin_day_and_closing_day(self):
        for key in ['equity_parent_begin','equity_parent']:
            c=synthetic_company(); c['accounts'][key]['period_end']='2022-12-30'
            self.assertEqual(metrics(c)['roe']['status'],'review_required')

    def test_bs_start_must_be_empty(self):
        c=synthetic_company(); c['accounts']['total_equity']['period_start']='2023-01-01'
        self.assertEqual(metrics(c)['debt_ratio']['status'],'review_required')

    def test_standalone_mapping_not_allowed_in_cfs(self):
        c=synthetic_company(); c['accounts']['net_income_parent'].update(match_method='standalone_mapping',mapped_from='net_income_total')
        self.assertEqual(metrics(c)['roe']['status'],'review_required')

    def test_cfs_parent_missing_not_replaced_with_total(self):
        c=synthetic_company(); c['accounts'].pop('net_income_parent'); out=metrics(c)
        self.assertEqual(out['roe']['status'],'missing'); self.assertEqual(out['net_margin']['status'],'computed')

    def test_context_invalid_dates_scope_basis_and_schema(self):
        changes=[('analysis_as_of',None),('analysis_as_of','2023-11-13'),('rcept_date','2023-11-13'),
                 ('period_start','2023-10-01'),('period_end','2023-12-31'),('period_start','2023-01-02'),
                 ('fs_div','bad'),('report_code','11011'),('period_date_basis','unknown'),('period_end','bad')]
        for field,value in changes:
            c=synthetic_company(); c['context'][field]=value
            self.assertTrue(all(m['status']=='review_required' for m in metrics(c).values()),field)
        for field,value in [('schema_version','legacy'),('measurement_basis','LTM'),('annualized',True)]:
            c=synthetic_company(); c[field]=value
            self.assertTrue(all(m['status']=='review_required' for m in metrics(c).values()))

    def test_wrong_context_types_actionable_error(self):
        for field in ['analysis_as_of','report_code','period_type','fs_div']:
            c=synthetic_company(); c['context'][field]=[]
            with self.assertRaises(ValueError): calculate_company(c)

    def test_nondecember_custom_period_opening_equity_verification(self):
        c=synthetic_company(); ctx=c['context']; ctx.update(period_start='2022-04-01',period_end='2022-12-31',period_date_basis='provided_dates')
        for key,a in c['accounts'].items():
            if a['statement_div']!='BS': a['period_start']='2022-04-01'
            a['period_end']='2022-03-31' if key.endswith('_begin') else '2022-12-31'
        out=metrics(c)
        self.assertEqual(out['roe']['status'],'review_required'); self.assertEqual(out['net_margin']['status'],'computed')
        self.assertNotIn('9개월',out['net_margin']['period_label'])
        ctx['opening_balance_date_verified']=True; self.assertEqual(metrics(c)['roe']['status'],'computed')

    def test_all_results_serialize_and_report_status(self):
        c=synthetic_company(); c['accounts'].pop('revenue'); out=calculate_company(c); json.dumps(out,allow_nan=False)
        for key,r in out['metrics'].items():
            self.assertEqual(r['input_keys'],list(METRICS[key][2]))
            if r['status']!='computed':
                self.assertIsNone(r['value']); self.assertIsNone(r['display_value']); self.assertTrue(r['reason'])


class DocumentAndCLITests(unittest.TestCase):
    def test_multicompany_and_comparison_warnings(self):
        a=synthetic_company(corp='00000001'); b=synthetic_company(scope='OFS',currency='USD',code='11012',corp='00000002')
        doc={'companies':{'00000001':a,'00000002':b},'rejected_reports':[{'reason':'합성 제외'}]}; out=calculate_document(doc)
        self.assertEqual(len(out['companies']),2); self.assertEqual(len(out['comparison_warnings']),3)
        self.assertEqual(out['rejected_reports'],doc['rejected_reports'])

    def test_integration_keeps_sources_and_handles_zero_and_missing(self):
        c=synthetic_company(); before=copy.deepcopy(c)
        out=build_finance_payload({'companies':{'00000001':c}})
        self.assertEqual(out['companies']['00000001']['accounts'], c['accounts'])
        self.assertEqual(c, before)
        r=out['companies']['00000001']['metrics']['cash_capex']
        self.assertEqual(ui_text(dict(r,value='0',display_value='0.00')), '0.0억 원')
        self.assertEqual(ui_text(dict(r,status='missing',value=None,display_value=None)), '자료 없음')

    def test_mixed_asof_dates_rejected(self):
        a=synthetic_company(); b=synthetic_company(corp='00000002'); b['context']['analysis_as_of']='2024-04-02'
        with self.assertRaises(ValueError): calculate_document({'companies':{'00000001':a,'00000002':b}})

    def test_bad_document_shapes_rejected(self):
        c=synthetic_company()
        for doc in [None,{}, {'companies':{}},{'companies':[]},{'companies':{'00000001':None}},
                    {'companies':{'wrong':c}},{'companies':{'00000001':dict(c,context=None)}}]:
            with self.assertRaises(ValueError): calculate_document(doc)

    def test_cli_success(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/'nested'/'out.json'
            r=subprocess.run([sys.executable,'-m','peerproof.finance.finance_metrics',str(HERE/'APR_latest_report_input.json'),'--output',str(output)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            actual=json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(actual,calculate_document(json.loads((HERE/'APR_latest_report_input.json').read_text(encoding='utf-8'))))

    def test_cli_refuses_overwriting_input(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'in.json'; content=(HERE/'APR_latest_report_input.json').read_text(encoding='utf-8')
            source.write_text(content, encoding='utf-8')
            r=subprocess.run([sys.executable,'-m','peerproof.finance.finance_metrics',str(source),'--output',str(source)],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0); self.assertEqual(source.read_text(encoding='utf-8'),content)

    def test_cli_rejects_legacy_and_bad_json(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'in.json'; output=Path(td)/'out.json'
            for content in ['{bad','{"periods":{}}']:
                source.write_text(content, encoding='utf-8')
                r=subprocess.run([sys.executable,'-m','peerproof.finance.finance_metrics',str(source),'--output',str(output)],capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0); self.assertFalse(output.exists())


class ConfirmedCapexAndDisplayTests(unittest.TestCase):
    CAPEX = {'cash_capex', 'simple_fcf', 'capex_to_revenue'}

    def test_intangible_missing_treated_as_zero_with_assumption(self):
        c=synthetic_company(); c['accounts']['intangible_purchase_cash'].update(status='missing', value=None)
        add_synthetic_zero_confirmation(c,'intangible_purchase_cash')
        out=metrics(c)
        self.assertEqual(Decimal(out['cash_capex']['value']), 30)
        self.assertEqual(Decimal(out['simple_fcf']['value']), 120)
        self.assertEqual(out['capex_to_revenue']['display_value'], '3.00')
        self.assertEqual(out['cash_capex']['normalized_inputs']['intangible_purchase_cash'], '0')
        for k, r in out.items():
            self.assertEqual(bool(r['assumptions']), k in self.CAPEX, k)

    def test_ppe_missing_treated_as_zero(self):
        c=synthetic_company(); c['accounts']['ppe_purchase_cash'].update(status='missing', value=None)
        add_synthetic_zero_confirmation(c,'ppe_purchase_cash')
        self.assertEqual(Decimal(metrics(c)['cash_capex']['value']), 10)

    def test_both_missing_stays_missing(self):
        c=synthetic_company()
        for k in ['ppe_purchase_cash','intangible_purchase_cash']: c['accounts'][k].update(status='missing', value=None)
        out=metrics(c)
        for k in self.CAPEX: self.assertEqual(out[k]['status'], 'missing'); self.assertIsNone(out[k]['value'])

    def test_ambiguous_or_invalid_never_zeroed(self):
        for state in ['ambiguous','invalid']:
            c=synthetic_company(); c['accounts']['intangible_purchase_cash'].update(status=state, value=None)
            out=metrics(c)
            for k in self.CAPEX: self.assertEqual(out[k]['status'], 'review_required'); self.assertFalse(out[k]['assumptions'])

    def test_zero_assumption_still_checks_found_component(self):
        # 남은 구성값의 기간/접수번호 오류는 그대로 잡아야 한다.
        c=synthetic_company(); c['accounts']['intangible_purchase_cash'].update(status='missing', value=None)
        add_synthetic_zero_confirmation(c,'intangible_purchase_cash')
        c['accounts']['ppe_purchase_cash']['rcept_no']='20231114009999'
        self.assertEqual(metrics(c)['cash_capex']['status'], 'review_required')

    def test_real_raon_fy2019_no_intangible_row(self):
        # v2가 제공한 라온 FY2019 숫자를 API 형태로 재구성한 입력. 원문 무지출 확인 기록은 없음.
        def r(aid, sj, cur, prev=None):
            x={'corp_code':'00000003','bsns_year':'2019','reprt_code':'11011','rcept_no':'20200330000456','sj_div':sj,
               'account_id':aid,'account_nm':aid,'currency':'KRW','thstrm_amount':cur}
            if prev is not None: x['frmtrm_amount']=prev
            return x
        rows=[r('ifrs-full_Revenue','IS','12632423500'), r('dart_OperatingIncomeLoss','IS','-1211469053'),
              r('ifrs-full_ProfitLoss','IS','-1431915408'), r('ifrs-full_Assets','BS','18754930175'),
              r('ifrs-full_Liabilities','BS','15457883995'), r('ifrs-full_Equity','BS','3297046180','4562003658'),
              r('ifrs-full_CashFlowsFromUsedInOperatingActivities','CF','-285756285'),
              r('ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities','CF','-140312090')]
        company=select_latest([extract_report({'fs_div':'OFS','statements':rows}, as_of='2021-04-08')])
        out=metrics(company)
        for k in self.CAPEX:
            self.assertEqual(out[k]['status'],'missing'); self.assertIsNone(out[k]['value'])
        self.assertEqual(out['roe']['display_value'], '-36.44')       # 적자 ROE는 계산
        self.assertEqual(out['debt_ratio']['display_value'], '468.84')
        self.assertEqual(out['cash_conversion']['status'], 'not_meaningful')  # 순이익 ≤ 0

    def test_format_amount(self):
        from peerproof.finance.integration_example import format_amount
        self.assertEqual(format_amount('8155992532','KRW'), '81.6억 원')
        self.assertEqual(format_amount(371789961905,'KRW'), '3,718억 원')
        self.assertEqual(format_amount('-897292937','KRW'), '-9.0억 원')
        self.assertEqual(format_amount('-1','KRW'), '0.0억 원')
        self.assertEqual(format_amount('1234567','USD'), '1,234,567 USD')

    def test_ui_text_marks_assumption(self):
        c=synthetic_company(); c['accounts']['intangible_purchase_cash'].update(status='missing', value=None)
        add_synthetic_zero_confirmation(c,'intangible_purchase_cash')
        self.assertTrue(ui_text(metrics(c)['cash_capex']).endswith(' *'))
        self.assertEqual(ui_text(metrics()['operating_margin']), '20.00%')


class FinalZeroAndDecimalTests(unittest.TestCase):
    def missing_company(self):
        c=synthetic_company(); c['accounts']['intangible_purchase_cash'].update(status='missing',value=None,raw_amount=None)
        return c

    def test_unverified_missing_does_not_default_to_zero(self):
        for key in ['ppe_purchase_cash','intangible_purchase_cash']:
            c=synthetic_company(); c['accounts'][key].update(status='missing',value=None,raw_amount=None)
            for k in ['cash_capex','simple_fcf','capex_to_revenue']:
                r=metrics(c)[k]; self.assertEqual(r['status'],'missing'); self.assertIsNone(r['value'])
                self.assertFalse(r['assumptions']); self.assertFalse(r['zero_confirmations'])

    def test_confirmed_zero_keeps_original_and_confirmation_evidence(self):
        c=self.missing_company(); proof=add_synthetic_zero_confirmation(c,'intangible_purchase_cash'); before=copy.deepcopy(c)
        out=metrics(c)
        self.assertEqual(c,before)
        for k in ['cash_capex','simple_fcf','capex_to_revenue']:
            r=out[k]; self.assertEqual(r['status'],'computed')
            self.assertEqual(r['source_inputs']['intangible_purchase_cash']['status'],'missing')
            self.assertEqual(r['normalized_inputs']['intangible_purchase_cash'],'0')
            self.assertEqual(r['zero_confirmations']['intangible_purchase_cash'],proof)
            self.assertTrue(ui_text(r).endswith(' *'))
        self.assertFalse(out['roe']['zero_confirmations'])

    def test_false_and_nonboolean_verification(self):
        for flag,expected in [(False,'missing'),('true','review_required'),(1,'review_required'),(None,'review_required')]:
            c=self.missing_company(); proof=add_synthetic_zero_confirmation(c,'intangible_purchase_cash'); proof['verified']=flag
            self.assertEqual(metrics(c)['cash_capex']['status'],expected)

    def test_confirmation_must_match_selected_report_and_have_location(self):
        changes={'corp_code':'00000002','rcept_no':'20231114009999','fs_div':'OFS',
                 'period_start':'2023-04-01','period_end':'2023-06-30','currency':'USD',
                 'source_url':'https://example.com','source_locator':'','note':'',
                 'conclusion':'row_not_found'}
        for field,value in changes.items():
            with self.subTest(field=field):
                c=self.missing_company(); proof=add_synthetic_zero_confirmation(c,'intangible_purchase_cash'); proof[field]=value
                out=metrics(c)
                for k in ['cash_capex','simple_fcf','capex_to_revenue']:
                    self.assertEqual(out[k]['status'],'review_required'); self.assertIsNone(out[k]['value'])
                self.assertEqual(out['roe']['status'],'computed')

    def test_malformed_confirmation_never_computed(self):
        for value in [[], True, {}, 'confirmed']:
            c=self.missing_company(); c['zero_cashflow_confirmations']={'intangible_purchase_cash':value}
            self.assertEqual(metrics(c)['cash_capex']['status'],'review_required')
        c=self.missing_company(); c['zero_cashflow_confirmations']=[]
        self.assertEqual(metrics(c)['cash_capex']['status'],'review_required')

    def test_nonzero_or_invalid_raw_amount_conflicts_with_confirmation(self):
        for field in ['raw_amount','value']:
            for value in [10,'10','bad',1.0,True]:
                c=self.missing_company(); add_synthetic_zero_confirmation(c,'intangible_purchase_cash')
                c['accounts']['intangible_purchase_cash'][field]=value
                self.assertEqual(metrics(c)['cash_capex']['status'],'review_required')

    def test_missing_row_metadata_still_checked(self):
        changes={'period_start':'2023-04-01','period_end':'2023-06-30','rcept_no':'20231114009999',
                 'fs_div':'OFS','currency':'USD','statement_div':'BS','amount_field':'frmtrm_amount','unit_multiplier':1000}
        for field,value in changes.items():
            c=self.missing_company(); add_synthetic_zero_confirmation(c,'intangible_purchase_cash'); c['accounts']['intangible_purchase_cash'][field]=value
            self.assertEqual(metrics(c)['cash_capex']['status'],'review_required',field)

    def test_confirmation_never_overrides_ambiguous_invalid_or_absent_key(self):
        for state in ['ambiguous','invalid']:
            c=self.missing_company(); add_synthetic_zero_confirmation(c,'intangible_purchase_cash'); c['accounts']['intangible_purchase_cash']['status']=state
            self.assertEqual(metrics(c)['cash_capex']['status'],'review_required')
        c=self.missing_company(); add_synthetic_zero_confirmation(c,'intangible_purchase_cash'); c['accounts'].pop('intangible_purchase_cash')
        self.assertEqual(metrics(c)['cash_capex']['status'],'missing')

    def test_two_missing_never_zeroed_even_with_confirmations(self):
        c=self.missing_company(); add_synthetic_zero_confirmation(c,'intangible_purchase_cash')
        c['accounts']['ppe_purchase_cash']['status']='missing'; add_synthetic_zero_confirmation(c,'ppe_purchase_cash')
        self.assertEqual(metrics(c)['cash_capex']['status'],'missing')

    def test_custom_account_mapping_failure_cannot_invent_zero(self):
        from peerproof.finance.finance_latest import ACCOUNT_RULES
        c=synthetic_company()
        # 원본에 실제로 10의 지출이 있지만 표준 ID와 제한된 이름 목록에는 없는 계정.
        rows=[{'corp_code':'00000001','bsns_year':'2023','reprt_code':'11014','rcept_no':'20231114001221',
               'sj_div':'CF','account_id':'custom_IntangibleCash','account_nm':'무형자산 취득 지출','currency':'KRW','thstrm_amount':'10'},
              {'corp_code':'00000001','bsns_year':'2023','reprt_code':'11014','rcept_no':'20231114001221',
               'sj_div':'CF','account_id':ACCOUNT_RULES['ppe_purchase_cash'][1][0],'currency':'KRW','thstrm_amount':'30'}]
        extracted=extract_report({'fs_div':'CFS','statements':rows},as_of='2024-04-01')
        c['accounts']['intangible_purchase_cash']=extracted['accounts']['intangible_purchase_cash']
        self.assertEqual(metrics(c)['cash_capex']['status'],'missing')

    def test_formatter_independent_of_global_precision_and_traps(self):
        from peerproof.finance.integration_example import format_amount
        expected=format_amount('8155992532','KRW')
        with localcontext() as ctx:
            ctx.prec=6; ctx.rounding=ROUND_DOWN; ctx.traps[Inexact]=True
            self.assertEqual(format_amount('8155992532','KRW'),expected)
            self.assertEqual(format_amount('123.5','USD'),'124 USD')

    def test_formatter_large_valid_values_and_invalid_inputs(self):
        from peerproof.finance.integration_example import format_amount
        value=10**100
        self.assertEqual(format_amount(str(value),'KRW'),f'{10**92:,}억 원')
        self.assertEqual(format_amount(str(value),'USD'),f'{value:,} USD')
        for bad in [None,1.0,True,'NaN','Infinity','bad']:
            with self.assertRaises(ValueError): format_amount(bad,'KRW')
        with self.assertRaises(ValueError): format_amount('10','krw')


class APRTests(unittest.TestCase):
    def check_apr(self, company):
        out=metrics(company)
        for key,value in {'cash_capex':'8155992532','simple_fcf':'52680804870'}.items(): self.assertEqual(Decimal(out[key]['value']),Decimal(value))
        displays={'operating_margin':'18.78','net_margin':'15.45','roe':'42.88','debt_ratio':'47.05',
                  'cash_conversion':'105.91','cfo_margin':'16.36','capex_to_revenue':'2.19'}
        for key,display in displays.items(): self.assertEqual(out[key]['display_value'],display,key)
        self.assertTrue(all(r['status']=='computed' for r in out.values()))
        self.assertEqual(out['roe']['source_inputs']['equity_parent_begin']['value'],99266311538)
        self.assertIn('9개월 누적',out['roe']['period_label'])

    def test_provided_apr_v3_output(self):
        doc=json.loads((HERE/'APR_latest_report_input.json').read_text(encoding='utf-8')); self.check_apr(doc['companies']['01190568'])

    @unittest.skipUnless(os.environ.get('PEERPROOF_DATA'),'PEERPROOF_DATA=data.zip이면 APR 원본 통합 실행')
    def test_real_apr_raw_to_metrics(self):
        reports=[extract_report(p,name,as_of='2023-12-21') for name,p in read_payloads(Path(os.environ['PEERPROOF_DATA']))]
        self.assertEqual(len(reports),3); self.check_apr(select_latest(reports))
        for r in reports:
            out=metrics(select_latest([r])); self.assertEqual(set(out),set(METRICS)); json.dumps(out,allow_nan=False)


if __name__=='__main__':
    unittest.main()
 