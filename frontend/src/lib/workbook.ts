import * as XLSX from "xlsx";
import type { Company, Mode, ParsedData, PerInput, ProfileRow, Settings } from "./types";

type Cell = unknown;
type Row = Cell[];

const SHEETS = { settings: "01_입력설정", companies: "05_기업입력", profile: "06_프로필근거" } as const;

const num = (v: Cell): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const str = (v: Cell): string => (v == null ? "" : String(v).trim());

/** 엑셀 날짜 일련번호 또는 문자열 → YYYY-MM-DD */
export function dateStr(v: Cell): string {
  if (typeof v === "number") return new Date(Date.UTC(1899, 11, 30) + Math.round(v) * 86400000).toISOString().slice(0, 10);
  if (v instanceof Date) return v.toISOString().slice(0, 10);
  return str(v).slice(0, 10);
}

function sheetRows(wb: XLSX.WorkBook, name: string): Row[] {
  const ws = wb.Sheets[name];
  if (!ws) throw new Error(`필수 시트 '${name}'를 찾을 수 없습니다. 올바른 Peer Proof 엑셀 양식인지 확인하세요.`);
  return XLSX.utils.sheet_to_json<Row>(ws, { header: 1, defval: null, raw: true });
}

function parseSettings(rows: Row[]): Settings {
  const map = new Map<string, Cell>();
  rows.forEach((r) => {
    const k = str(r[0]);
    if (k && !map.has(k)) map.set(k, r[1]);
  });
  const need = (label: string): Cell => {
    if (!map.has(label)) throw new Error(`01_입력설정에서 '${label}' 항목을 찾을 수 없습니다.`);
    return map.get(label);
  };
  const n = (label: string) => num(need(label)) ?? NaN;
  const mode = str(need("계산 모드")) === "확정" ? "확정" : ("예시" as Mode);
  return {
    targetId: str(need("대상기업 ID")),
    targetName: str(need("대상기업명")),
    industry: str(need("선택 산업")),
    asOf: dateStr(need("평가기준일")),
    period: str(need("이익 비교기간")),
    currency: str(need("통화")),
    fsBasis: str(need("재무제표 기준")),
    mode,
    weights: { bm: n("비즈니스모델 가중치"), growth: n("성장성 가중치"), risk: n("리스크 가중치"), fin: n("재무 가중치") },
    indThreshold: n("산업 코사인 임계값"),
    indTopN: n("산업 후보 상한 N"),
    bmThreshold: n("BM 코사인 임계값"),
    bmTopN: n("BM 후보 상한 N"),
    minPeers: n("최소 PER 비교기업 수"),
    perCap: n("허용 PER 상한"),
    discMax: n("하단 할인율 (최대)"),
    discMin: n("상단 할인율 (최소)"),
    roundUnit: n("가격 절사 단위 (원)"),
    finTol: n("재무 비율 차이 허용폭"),
    growthTol: n("성장률 차이 허용폭"),
    minEvidence: n("최소 근거 충족률"),
    netIncome: n("귀속 당기순이익 (원)"),
    sharesPre: n("IPO 전 기준 주식수 (주)"),
    sharesNew: n("신주 발행 수 (주)"),
    sharesSecondary: n("구주 매출 수 (주)"),
    sharesDilution: n("추가 희석 주식수 (주)"),
    earningsStatus: str(need("대상기업 이익 검증 상태")),
    sharesStatus: str(need("대상기업 주식수 검증 상태")),
    targetSource: str(need("대상기업 원천 문서")),
    normAdj: n("정상화 이익 조정액 (원)"),
    normNote: str(need("정상화 조정 근거")),
    profileVersion: str(need("프로필/점수 버전")),
    embeddingModel: str(need("임베딩 모델·버전")),
    llmModel: str(need("LLM 모델·버전")),
  };
}

/** 'header' 행을 찾아 그 아래 연속 데이터 행을 {헤더: 값} 으로 반환 */
function tableAt(rows: Row[], headerIdx: number): Record<string, Cell>[] {
  const head = rows[headerIdx].map(str);
  const out: Record<string, Cell>[] = [];
  for (let i = headerIdx + 1; i < rows.length; i++) {
    if (str(rows[i][0]) === "") break;
    const rec: Record<string, Cell> = {};
    head.forEach((h, c) => h && (rec[h] = rows[i][c]));
    out.push(rec);
  }
  return out;
}

function headerRows(rows: Row[]): number[] {
  return rows.map((r, i) => (str(r[0]) === "기업 ID" ? i : -1)).filter((i) => i >= 0);
}

export function parseWorkbook(data: ArrayBuffer | Uint8Array): ParsedData {
  const wb = XLSX.read(data, { type: "array" });
  const settings = parseSettings(sheetRows(wb, SHEETS.settings));

  const crow = sheetRows(wb, SHEETS.companies);
  const hs = headerRows(crow);
  if (hs.length < 2) throw new Error("05_기업입력에서 기업 표와 PER 입력 표를 찾을 수 없습니다.");
  const companies: Company[] = tableAt(crow, hs[0]).map((r) => ({
    id: str(r["기업 ID"]),
    name: str(r["기업명"]),
    industry: str(r["산업 설명"]),
    indCos: num(r["산업 코사인"]),
    bmCos: num(r["BM 코사인"]),
    growth: num(r["매출 성장률"]),
    riskCos: num(r["리스크 코사인"]),
    opMargin: num(r["영업이익률"]),
    debtRatio: num(r["부채 / 자산"]),
    evidence: num(r["근거 충족률"]),
    status: str(r["근거 검증 상태"]),
    source: str(r["원천 / 근거 위치"]),
    date: dateStr(r["공개일 / 기준일"]),
    memo: str(r["검토 메모"]),
  }));
  const perInputs: PerInput[] = tableAt(crow, hs[1]).map((r) => ({
    id: str(r["기업 ID"]),
    marketCap: num(r["시가총액 (원)"]),
    earnings: num(r["정상화 귀속 이익 (원)"]),
    period: str(r["이익 비교기간"]),
    currency: str(r["통화"]),
    basis: str(r["재무 기준"]),
    asOf: dateStr(r["시총 기준일"]),
    status: str(r["재무 검증 상태"]),
    source: str(r["원천 / 조정 근거"]),
    selected: num(r["PER 선택 1/0"]) === 1,
    reason: str(r["선택 / 제외 이유"]),
  }));

  const prow = sheetRows(wb, SHEETS.profile);
  const ph = headerRows(prow)[0];
  if (ph == null) throw new Error("06_프로필근거에서 헤더를 찾을 수 없습니다.");
  const profile: ProfileRow[] = tableAt(prow, ph)
    .filter((r) => str(r["영역"]) !== "")
    .map((r) => ({
      companyId: str(r["기업 ID"]),
      area: str(r["영역"]),
      key: str(r["필드 키"]),
      value: str(r["필드 값 / 예시"]),
      period: str(r["기간 / 기준"]),
      inputStatus: str(r["입력 상태"]),
      evidenceId: str(r["근거 ID"]),
      extractStatus: str(r["추출 상태"]),
      definition: str(r["정의 / 원문 위치"]),
      reviewer: str(r["검토자"]),
    }));

  if (!companies.some((c) => c.id === settings.targetId))
    throw new Error(`05_기업입력에 대상기업 ID '${settings.targetId}' 행이 없습니다.`);
  return { settings, companies, perInputs, profile };
}
