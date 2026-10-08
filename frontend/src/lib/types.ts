export type AreaKey = "bm" | "growth" | "risk" | "fin";
export type Weights = Record<AreaKey, number>;
export type Mode = "예시" | "확정";

export interface Settings {
  targetId: string;
  targetName: string;
  industry: string;
  asOf: string; // YYYY-MM-DD
  period: string;
  currency: string;
  fsBasis: string;
  mode: Mode;
  weights: Weights; // 파일 기본값 (분수, 합계 1)
  indThreshold: number;
  indTopN: number;
  bmThreshold: number;
  bmTopN: number;
  minPeers: number;
  perCap: number;
  discMax: number; // 하단 할인율 (최대)
  discMin: number; // 상단 할인율 (최소)
  roundUnit: number;
  finTol: number;
  growthTol: number;
  minEvidence: number;
  netIncome: number; // 원
  sharesPre: number; // 주
  sharesNew: number;
  sharesSecondary: number;
  sharesDilution: number;
  earningsStatus: string;
  sharesStatus: string;
  targetSource: string;
  normAdj: number; // 원
  normNote: string;
  profileVersion: string;
  embeddingModel: string;
  llmModel: string;
}

export interface Company {
  id: string;
  name: string;
  industry: string;
  indCos: number | null;
  bmCos: number | null;
  growth: number | null;
  riskCos: number | null;
  opMargin: number | null;
  debtRatio: number | null;
  evidence: number | null;
  status: string;
  source: string;
  date: string;
  memo: string;
}

export interface PerInput {
  id: string;
  marketCap: number | null;
  earnings: number | null;
  period: string;
  currency: string;
  basis: string;
  asOf: string;
  status: string;
  source: string;
  selected: boolean;
  reason: string;
}

export interface ProfileRow {
  companyId: string;
  area: string;
  key: string;
  value: string;
  period: string;
  inputStatus: string;
  evidenceId: string;
  extractStatus: string;
  definition: string;
  reviewer: string;
}

export interface ParsedData {
  settings: Settings;
  companies: Company[];
  perInputs: PerInput[];
  profile: ProfileRow[];
}
