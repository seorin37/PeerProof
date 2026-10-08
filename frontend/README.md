# Peer Proof Frontend

IPO 대상기업 공시 → Business Profile → Late Fusion(BGE-M3 임베딩 + 언어네트워크) Top 5 유사기업 → RAG+LLM 비교 설명 → PER 비교.
React 18 + TypeScript + Vite. 백엔드(FastAPI)가 완성되기 전에는 **Mock JSON**으로 동작합니다.

## 실행
```bash
npm install
npm run dev        # http://localhost:5173 (기본: mock 모드)
npm test           # vitest
npm run build
```

## Mock / Live 전환
`.env.example` 을 `.env.local` 로 복사해 사용합니다.
- `VITE_API_MODE=mock` (기본) / `live`
- `VITE_API_BASE_URL=/api`, `VITE_PROXY_TARGET=http://localhost:8000` (dev 프록시)

Mock 상태 시험: 주소 뒤에 `?mock=error` · `?mock=empty` · `?mock=slow`
특정 자원만: `?mock=error:similar,network` (자원: companies, profile, similar, network, explanation, valuation)

## 구조 — 백엔드가 바뀔 때 고칠 곳
API 경로·JSON 필드는 **확정되지 않았다고 가정**합니다.
- `src/types/domain.ts` : 화면용 도메인 타입(점수 0–100). 백엔드 DTO와 독립.
- `src/api/routes.ts` : 엔드포인트 경로 (PROVISIONAL). **경로 변경 시 여기만 수정.**
- `src/api/adapters.ts` : 백엔드 JSON → 도메인 변환 (가정: snake_case). **필드 변경 시 여기만 수정.**
- `src/api/mock.ts`, `src/mocks/*.json` : 가상 예시 데이터
- `src/hooks/useResource.ts`, `components/AsyncBoundary.tsx` : 로딩/오류/데이터 없음 처리
- `src/components/*`, `src/steps/*` : 화면 (API 형식을 직접 알지 못함)

## 참고
이전 Excel 기반 구현은 `feature/frontend` 의 이전 커밋에 남아 있습니다. 모든 Mock 값은 가상 예시입니다.
