/**
 * 프론트엔드가 소유하는 화면용 데이터 타입(도메인 모델).
 * 백엔드 JSON 구조와 무관하며, 백엔드 스키마가 바뀌면 api/adapters.ts 만 수정합니다.
 * 점수는 모두 0–100 스케일로 통일합니다(변환은 어댑터에서).
 */

export interface CompanySummary {
  id: string;
  name: string;
  /** 산업 선택 칩용 대분류(예: 반도체·전자). 없으면 산업 선택 영역을 숨김 */
  sector?: string;
  industry?: string;
  market?: string;
}

/** 모든 설명·프로필 값에 붙는 공시 근거 */
export interface EvidenceRef {
  id: string;
  source: string;
  locator?: string;
  url?: string;
  publishedAt?: string;
  quote?: string;
}

export interface ProfileItem {
  key: string;
  label: string;
  /** 표시용 문자열. 근거가 없어 비어 있으면 어댑터가 '미확인'으로 채움 */
  value: string;
  evidenceIds: string[];
  status?: string;
}

export interface ProfileSection {
  key: string;
  label: string;
  items: ProfileItem[];
}

export interface BusinessProfile {
  companyId: string;
  companyName: string;
  industry?: string;
  period?: string;
  basis?: string;
  version?: string;
  generatedAt?: string;
  summary?: string;
  sections: ProfileSection[];
  evidence: EvidenceRef[];
}

export type AreaKey = "bm" | "growth" | "risk" | "fin";
export type AreaScores = Record<AreaKey, number>;

export interface SimilarityScores {
  /** 영역별(Business Model/Growth/Risk/Finance) 임베딩 유사도 (0–100). 없으면 null → 중요도 가중 재계산 불가 */
  areas?: AreaScores | null;
  /** Late Fusion 결과 (0–100) */
  fused: number;
  /** BGE-M3 임베딩 유사도 (0–100). 없으면 null */
  embedding: number | null;
  /** 언어네트워크 유사도 (0–100). 없으면 null */
  network: number | null;
}

export interface SimilarCompany {
  rank: number;
  company: CompanySummary;
  scores: SimilarityScores;
}

export interface SimilarResult {
  targetId: string;
  fusion?: { embeddingWeight: number; networkWeight: number; method?: string };
  items: SimilarCompany[];
}

export interface NetworkNode {
  id: string;
  label: string;
  /** 중심성 (0–1) */
  centrality: number;
  group?: string;
}

export interface NetworkEdge {
  source: string;
  target: string;
  weight: number;
}

export interface CompanyNetwork {
  companyId: string;
  nodes: NetworkNode[];
  edges: NetworkEdge[];
}

/** 영역별 선정 근거 한 장: 설명 문장 + 대상/비교기업 수치 비교 + 근거 */
export interface AreaExplanation {
  area: AreaKey;
  /** 0–100. 없으면 유사도 결과의 영역 점수를 사용 */
  score: number | null;
  text: string;
  compare: { targetLabel: string; targetValue: string; peerLabel: string; peerValue: string } | null;
  evidenceIds: string[];
}

export interface Explanation {
  targetId: string;
  peerId: string;
  areas: AreaExplanation[];
  evidence: EvidenceRef[];
  /** 자료 충족률(0–100). 백엔드가 주면 표시 */
  coverage?: number | null;
  /** 기준 기간 · 회계 범위 · 단위 (예: 2025년 연결 · KRW / 억 원 및 %) */
  period?: string;
  generatedAt?: string;
  model?: string;
}

export interface PerPeer {
  companyId: string;
  name: string;
  per: number | null;
  pbr?: number | null;
  included: boolean;
  note?: string;
}

export interface PerStats {
  min: number | null;
  q1: number | null;
  median: number | null;
  mean: number | null;
  q3: number | null;
  max: number | null;
}

export interface Valuation {
  targetId: string;
  currency?: string;
  basis?: string;
  peers: PerPeer[];
  /** 백엔드가 주지 않으면 null → 화면에서 포함 기업 PER로 대신 계산해 표시 */
  stats: PerStats | null;
  /** 대상기업 순이익 (억원). 없으면 화면에서 직접 입력 */
  netIncome?: number | null;
  /** 기존 발행주식수 (만주). 없으면 화면에서 직접 입력 */
  shares?: number | null;
  notes: string[];
}
