#!/usr/bin/env bash
# PeerProof 일요일 실행 순서 (DART document.xml 이 열린 뒤)
#
# 사용:  bash scripts/run_sunday.sh <단계>      (단계를 안 주면 도움말)
#   1test    에이피알 1곳만 끝까지 돌려 본다 (시간·오류 확인용)
#   2batch   후보 전체 프로필 생성 (끝난 회사는 건너뛴다 → 중간에 끊겨도 다시 실행하면 이어서 한다)
#   3export  프로필 -> 유사도 입력
#   4sim     10번(BGE) + 11번(언어 네트워크, 화면용 그래프 포함)
#   5compare 방법별 비교 + 융합 가중치 근거 (정답지는 평가에만 사용)
#   6eval    후보 선별 단계 평가
#   7serve   화면용 JSON 만들기 (WEIGHTS="임베딩 네트워크" 로 5번에서 고른 값을 준다)
#   8run     API 서버(8000) 실행. 프론트는 다른 터미널에서  cd frontend && VITE_API_MODE=live npm run dev
#
# 바꿀 값은 아래 변수만. 환경변수로 덮어써도 된다.   예)  CANDIDATES=docs/evaluation/my.json bash scripts/run_sunday.sh 2batch
# 여러 사람이 나눠 돌릴 때:  START=0 LIMIT=7 bash scripts/run_sunday.sh 2batch   (팀원은 START=7 LIMIT=7 ...)
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="${TARGET:-에이피알}"
STOCK_CODE="${STOCK_CODE:-278470}"
AS_OF="${AS_OF:-20231221}"
CANDIDATES="${CANDIDATES:-docs/evaluation/apr_candidates_v0.json}"
ANSWER_KEY="${ANSWER_KEY:-docs/evaluation/apr_answer_key.json}"
SKIP="${SKIP:-growth risk}"                 # 시간 절약. 사업모델만 쓰면 growth risk 를 건너뛴다
START="${START:-0}"
LIMIT="${LIMIT:-}"
WEIGHTS="${WEIGHTS:-}"                       # 7serve 에서 필요: 예) WEIGHTS="0.5 0.5"
SIM_DIR="data/similarity_input"
GRAPH_DIR="data/similarity_input/network_graphs"
EVAL_DIR="data/evaluation"
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"

step="${1:-}"
case "$step" in
  1test)
    python scripts/build_profile.py --company "$TARGET" --stock-code "$STOCK_CODE" --as-of "$AS_OF" --skip $SKIP
    ;;
  2batch)
    extra=(--start "$START")
    [ -n "$LIMIT" ] && extra+=(--limit "$LIMIT")
    python scripts/build_profiles_batch.py --companies "$CANDIDATES" --as-of "$AS_OF" --skip $SKIP "${extra[@]}"
    python scripts/build_profiles_batch.py --companies "$CANDIDATES" --as-of "$AS_OF" --summary-only
    ;;
  3export)
    python scripts/export_similarity_inputs.py --target "$TARGET" --candidates "$CANDIDATES" --as-of "$AS_OF"
    ;;
  4sim)
    mkdir -p "$SIM_DIR" "$GRAPH_DIR"
    python experiments/pilot_ipo/scripts/10_bge_similarity.py \
      --target-profile "$SIM_DIR/target_profile.json" --candidates "$SIM_DIR/candidate_profiles.json" \
      --output "$SIM_DIR/bge_result.json"
    python experiments/pilot_ipo/scripts/11_language_network_similarity.py \
      --target-profile "$SIM_DIR/target_profile.json" --candidates "$SIM_DIR/candidate_profiles.json" \
      --output "$SIM_DIR/network_result.json" --graphs-dir "$GRAPH_DIR"
    ;;
  5compare)
    mkdir -p "$EVAL_DIR"
    python scripts/compare_methods.py --answer-key "$ANSWER_KEY" --candidates "$CANDIDATES" \
      --bge "$SIM_DIR/bge_result.json" --network "$SIM_DIR/network_result.json" \
      --out "$EVAL_DIR/method_comparison.json"
    ;;
  6eval)
    mkdir -p "$EVAL_DIR"
    python scripts/evaluate_candidates.py --answer-key "$ANSWER_KEY" --pool "$CANDIDATES" \
      --out "$EVAL_DIR/candidate_evaluation.json"
    ;;
  7serve)
    if [ -z "$WEIGHTS" ]; then
      echo "WEIGHTS 가 필요합니다. 5compare 결과로 고른 값을 주세요.  예) WEIGHTS=\"0.5 0.5\" bash scripts/run_sunday.sh 7serve" >&2
      exit 1
    fi
    python scripts/build_serving_data.py --target "$TARGET" --candidates "$CANDIDATES" --as-of "$AS_OF" \
      --bge "$SIM_DIR/bge_result.json" --network "$SIM_DIR/network_result.json" \
      --network-graphs "$GRAPH_DIR" --fusion-weights $WEIGHTS
    ;;
  8run)
    uvicorn peerproof.api.app:app --port 8000
    ;;
  *)
    sed -n '2,15p' "$0"
    ;;
esac
