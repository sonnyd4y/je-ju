"""FastAPI 서버. 실행: uvicorn app.api.main:app --port 8000  →  브라우저에서 http://localhost:8000

  GET  /                   웹 화면 (app/static/index.html)

  POST /api/chat           Agent 대화 (multipart: message, mode, session_id, image) → SSE 스트림
  GET  /api/stores         가게 목록 (지도용)
  GET  /api/stores/find    가게 찾기
  GET  /api/insight        지역 상권 요약
  GET  /api/crowd          혼잡 예측
  GET  /api/balance        생활권 과밀도
  GET  /api/health         상태 확인
"""
import json
import os
import uuid

from datetime import date

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.agent import loop
from app.data import db
from app.tools import cards, insight, stores

app = FastAPI(title="제주 동네가게 AI Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,capacitor://localhost,http://localhost").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS: dict[str, loop.Session] = {}
MAX_IMAGE_BYTES = 5 * 1024 * 1024

# 공개 데모 보호: 접속 코드(설정했을 때만)와 하루 대화 한도. 로컬 실행에는 영향 없음
ACCESS_CODE = os.getenv("DEMO_ACCESS_CODE", "").strip()
DAILY_LIMIT = int(os.getenv("DEMO_DAILY_LIMIT", "300"))
_usage = {"day": "", "count": 0}


def _guard(code: str | None):
    if ACCESS_CODE and (code or "").strip() != ACCESS_CODE:
        raise HTTPException(401, "접속 코드가 필요합니다.")
    today = date.today().isoformat()
    if _usage["day"] != today:
        _usage.update(day=today, count=0)
    if _usage["count"] >= DAILY_LIMIT:
        raise HTTPException(429, "오늘 데모 사용량이 다 찼습니다. 내일 다시 이용해 주세요.")
    _usage["count"] += 1


@app.on_event("startup")
def warm_up():
    # 혼잡 등급 기준선을 미리 계산해 첫 요청이 느리지 않게 한다
    try:
        insight._crowd_thresholds()
    except Exception as e:
        print(f"[warm-up] 건너뜀: {e}")


@app.get("/api/health")
def health():
    try:
        n = db.rows("SELECT count(*) n FROM stores WHERE status LIKE '영업%'")[0]["n"]
        db_ok = True
    except Exception:
        n, db_ok = 0, False
    return {
        "db": db_ok,
        "open_stores": n,
        "claude_key": bool(os.getenv("ANTHROPIC_API_KEY")),
        "access_code_required": bool(ACCESS_CODE),
        "model": loop.MODEL,
        "sources": list(db.sources().values()),
    }


@app.post("/api/chat")
async def chat(
    message: str = Form(""),
    mode: str = Form(""),
    session_id: str = Form(""),
    image: UploadFile | None = File(None),
    x_access_code: str | None = Header(None),
):
    _guard(x_access_code)
    sid = session_id or uuid.uuid4().hex
    session = SESSIONS.setdefault(sid, loop.Session(mode=mode, session_id=sid))
    data, media_type = None, ""
    if image is not None:
        data = await image.read()
        media_type = image.content_type or ""
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "사진은 5MB 이하로 올려 주세요.")
        if media_type not in loop.IMAGE_TYPES:
            raise HTTPException(415, "jpg, png, webp 사진만 올릴 수 있습니다.")
    if not message.strip() and data is None:
        raise HTTPException(400, "메시지나 사진이 필요합니다.")

    async def events():
        yield _sse({"type": "session", "session_id": sid})
        if session.lock.locked():
            yield _sse({"type": "error", "message": "이전 질문을 처리하는 중입니다. 잠시만 기다려 주세요."})
            return
        async with session.lock:
            async for ev in loop.run(session, message, data, media_type):
                yield _sse(ev)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def _sse(ev: dict) -> str:
    return f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"


def _ok(out: dict) -> dict:
    if "error" in out:
        raise HTTPException(404, out["error"])
    return out


@app.get("/api/stores")
def api_stores(region: str = "", category: str = "", opened_after: str = "", unlisted_only: bool = False,
               keyword: str = "", limit: int = 50):
    return _ok(stores.search_stores(region, category, opened_after, unlisted_only, keyword, limit))


@app.get("/api/stores/find")
def api_find(name: str, address_hint: str = ""):
    return stores.find_store(name, address_hint)


@app.get("/api/insight")
def api_insight(region: str):
    return _ok(insight.area_insight(region))


@app.get("/api/crowd")
def api_crowd(region: str, weekday: str = "", time_slot: str = ""):
    return _ok(insight.predict_crowd(region, weekday, time_slot))


@app.get("/api/cards/{name}")
def api_card(name: str):
    """render_card가 만든 이미지. 파일 이름만 받는다 (경로 이동 방지)."""
    path = (cards.OUT / name).resolve()
    if path.parent != cards.OUT.resolve() or path.suffix != ".png" or not path.exists():
        raise HTTPException(404, "이미지 없음")
    return FileResponse(path, media_type="image/png")


@app.get("/api/balance")
def api_balance(region: str):
    return _ok(insight.resident_balance(region))


# 웹 화면 (API 경로보다 뒤에 붙여야 /api/* 가 먼저 처리된다)
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "static", html=True), name="web")
