export const won = (n: number | null | undefined) => (n == null ? "—" : Math.round(n).toLocaleString("ko-KR"));
export const eok = (n: number | null | undefined) =>
  n == null ? "—" : (n / 1e8).toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
export const pct1 = (n: number | null | undefined) => (n == null ? "N/A" : (n * 100).toFixed(1) + "%");
export const x1 = (n: number | null | undefined, d = 1) => (n == null ? "N/A" : n.toFixed(d) + "×");

/** 숫자 입력 문자열 → number (콤마 허용, 빈 값은 0) */
export function parseNum(s: string, allowNegative = false): number {
  const cleaned = s.replace(/[^\d.-]/g, "");
  const v = Number(cleaned === "" || cleaned === "-" ? 0 : cleaned);
  if (!Number.isFinite(v)) return 0;
  return allowNegative ? v : Math.max(0, v);
}

const KEY_LABELS: [RegExp, string][] = [
  [/products$/, "제품 · 서비스"], [/customers$/, "고객 유형"], [/revenue_model$/, "수익 모델"], [/channels$/, "유통 채널"],
  [/value_chain$/, "가치사슬"], [/differentiation$/, "차별화 요소"], [/revenue_yoy$/, "매출 성장률"], [/market$/, "시장 환경"],
  [/drivers$/, "성장 동인"], [/expansion$/, "확장 방향"], [/risk\.customer$/, "고객 집중"], [/competition$/, "경쟁 구도"],
  [/regulatory$/, "규제"], [/operations$/, "운영 의존"], [/financial\.revenue$/, "매출액"], [/operating_ma/, "영업이익률"],
  [/liabilities_/, "부채 / 자산"], [/net_income/, "귀속 당기순이익"], [/shares_pre/, "IPO 전 주식수"],
  [/source_url$/, "공시 URL"], [/locator$/, "원문 위치"], [/quote$/, "원문 발췌"], [/published_at$/, "공개일"], [/version$/, "프로필 버전"],
];
export const keyLabel = (key: string) => KEY_LABELS.find(([re]) => re.test(key))?.[1] ?? key;

/** 프로필 값 표시 형식: 비율·금액·주식수는 단위를 붙여 보여준다 */
export function profileValue(key: string, raw: string): string {
  const n = Number(raw);
  if (raw === "" || !Number.isFinite(n)) return raw || "미확인";
  if (/yoy|margin|operating_ma|liabilities_/.test(key)) return pct1(n);
  if (/shares/.test(key)) return won(n) + " 주";
  if (/revenue$|net_income/.test(key)) return eok(n) + " 억 원";
  return raw;
}
