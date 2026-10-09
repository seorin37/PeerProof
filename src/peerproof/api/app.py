"""
프론트엔드용 읽기 전용 API (FastAPI)

scripts/build_serving_data.py 가 만든 JSON 파일을 그대로 돌려준다.
프론트엔드(Vite) 프록시는 /api 를 경로 변경 없이 넘기므로 모든 경로가 /api 로 시작한다.

실행:  uvicorn peerproof.api.app:app --port 8000   (PYTHONPATH=src, PEERPROOF_SERVING_DIR로 폴더 변경 가능)
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

SAFE_ID = re.compile(r"^[0-9A-Za-z_\-]+$")
DEFAULT_DIR = Path("data") / "serving"


def create_app(serving_dir: Path | str | None = None) -> FastAPI:
    base = Path(serving_dir or os.getenv("PEERPROOF_SERVING_DIR") or DEFAULT_DIR)
    app = FastAPI(title="PeerProof API")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["GET"], allow_headers=["*"])
    router = APIRouter(prefix="/api")

    def load(*parts: str):
        for part in parts:
            if not SAFE_ID.match(part.removesuffix(".json")):
                raise HTTPException(status_code=400, detail="잘못된 식별자입니다.")
        path = base.joinpath(*parts)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"자료가 없습니다: {'/'.join(parts)}")
        return json.loads(path.read_text(encoding="utf-8"))

    @router.get("/companies")
    def companies(query: str | None = None):
        items = load("companies.json")
        if query:
            needle = query.strip().lower()
            items = [c for c in items if needle in str(c.get("name", "")).lower()]
        return items

    @router.get("/companies/{company_id}/profile")
    def profile(company_id: str):
        return load(company_id, "profile.json")

    @router.get("/companies/{company_id}/similar")
    def similar(company_id: str):
        return load(company_id, "similar.json")

    @router.get("/companies/{company_id}/network")
    def network(company_id: str):
        # 후보기업의 네트워크는 아직 만들지 않았다 -> 404 대신 빈 네트워크를 주면 화면이 "데이터 없음"으로 표시한다
        path = base / company_id / "network.json"
        if SAFE_ID.match(company_id) and not path.exists():
            return {"company_id": company_id, "nodes": [], "edges": []}
        return load(company_id, "network.json")

    @router.get("/companies/{company_id}/explanations/{peer_id}")
    def explanation(company_id: str, peer_id: str):
        # 비교 설명(RAG+LLM)은 아직 만들지 않았다 -> 빈 설명을 주면 화면이 "아직 없음"으로 표시한다
        path = base / company_id / f"explanation_{peer_id}.json"
        if SAFE_ID.match(company_id) and SAFE_ID.match(peer_id) and not path.exists():
            return {"target_id": company_id, "peer_id": peer_id, "summary": "", "similarities": [], "differences": [], "evidence": []}
        return load(company_id, f"explanation_{peer_id}.json")

    @router.get("/companies/{company_id}/valuation")
    def valuation(company_id: str):
        return load(company_id, "valuation.json")

    @router.get("/companies/{company_id}/metrics")
    def metrics(company_id: str):
        return load(company_id, "metrics.json")

    app.include_router(router)
    return app


app = create_app()
