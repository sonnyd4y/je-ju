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
from app.tools import cards, drafts, insight, naver, places, recommend, reviews, stores

app = FastAPI(title="제주 동네가게 AI Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:8000,http://localhost,capacitor://localhost,"
                                         "https://jeju-local-agent.web.app,https://jeju-local-agent.firebaseapp.com").split(","),
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

    # 수요 예측 모델(불러오기 수 초)과 오늘 예측은 뒤에서 미리 준비 — 서버는 바로 응답 가능
    def _preload():
        try:
            from app.tools import forecast
            if forecast._load():
                forecast._day_preds(date.today().isoformat())
        except Exception as e:
            print(f"[warm-up] 예측 모델 건너뜀: {e}")
    import threading
    threading.Thread(target=_preload, daemon=True).start()


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


@app.get("/api/recommend")
def api_recommend(regions: str, category: str = "", when: str = "", time_slot: str = "", priority: str = "", limit: int = 8):
    """관광객 추천 의사결정 모델을 AI 없이 바로 호출 (화면용, 비용 0)."""
    return _ok(recommend.recommend_stores(regions, category, when, time_slot, priority, limit))


@app.post("/api/naver/link")
def api_naver_link(body: dict):
    try:
        sid = int(body.get("store_id"))
    except (TypeError, ValueError):
        raise HTTPException(400, "store_id(숫자)가 필요합니다.")
    return _ok(naver.link_naver_name(sid, str(body.get("naver_name") or "")[:60], bool(body.get("confirm", True))))


@app.get("/api/naver")
def api_naver(store_id: int):
    return _ok(naver.check_naver_listed(store_id))


@app.get("/api/map")
def api_map(when: str = "", time_slot: str = "점심", kinds: str = "관광지,오름,해수욕장,명소", store_regions: str = "애월,한림,구좌"):
    return places.map_data(when, time_slot, kinds, store_regions)


@app.get("/api/itinerary")
def api_itinerary(regions: str, when: str = "", start: str = "10:00", stops: int = 3,
                  kinds: str = "관광지,오름,해수욕장,명소", meals: str = "점심", category: str = ""):
    return _ok(places.plan_itinerary(regions, when, start, stops, kinds, meals, category))


@app.get("/api/nearby")
def api_nearby(lat: float, lng: float, when: str = "", time_slot: str = "점심", radius_km: float = 3.0):
    if not (33.0 <= lat <= 34.0 and 126.0 <= lng <= 127.2):
        raise HTTPException(400, "제주 안에서만 쓸 수 있어요")
    # 정밀 좌표가 와도 약 100m 단위로만 쓴다
    return places.nearby(round(lat, 3), round(lng, 3), when, time_slot, min(max(radius_km, 0.5), 10))


@app.post("/api/reviews/analyze")
def api_review_text(body: dict):
    text = str(body.get("text") or "")[:30000]
    return _ok(reviews.analyze_review_text(text))


@app.get("/api/itinerary/candidates")
def api_itinerary_candidates(regions: str, when: str = ""):
    return places.candidates(regions, when)


@app.post("/api/itinerary/schedule")
def api_itinerary_schedule(body: dict):
    """화면에서 고친 일정(순서·머무는 시간·추가·삭제)의 시간과 이동을 다시 계산 (AI 없음)."""
    stops = body.get("stops") or []
    if not isinstance(stops, list) or len(stops) > 12:
        raise HTTPException(400, "장소는 12곳까지")
    return places.schedule(stops, str(body.get("start") or "10:00")[:5])


@app.get("/api/store/{store_id}")
def api_store(store_id: int):
    """사장님 내 가게 화면: 가게 정보·네이버 등록·동네 손님·요일×시간 혼잡·리뷰 요약·만든 초안 (AI 없음)."""
    rows = db.rows("SELECT store_id, name, category, open_date, status, city, emd, addr_road, addr_jibun, lat, lng "
                   "FROM stores WHERE store_id=?", [store_id])
    if not rows:
        raise HTTPException(404, "가게 없음")
    s = rows[0]
    region = f"{s['city']} {s['emd']}"
    rv = reviews.analyze_reviews(s["name"])
    # 우리 동네에 최근 1년 새로 생긴 가게 (인허가 기준일부터 1년)
    asof = db.rows("SELECT max(open_date) d FROM stores")[0]["d"]
    newbies = db.rows(
        "SELECT name, category, open_date, addr_road FROM stores WHERE status LIKE '영업%' AND city=? AND emd=? "
        "AND open_date >= date(?, '-1 year') AND store_id != ? ORDER BY (category = ?) DESC, open_date DESC LIMIT 12",
        [s["city"], s["emd"], asof, store_id, s["category"]])
    return {
        "store": s,
        "naver": naver.check_naver_listed(store_id),
        "insight": insight.area_insight(region),
        "crowd": insight.predict_crowd(region),
        "reviews": rv if "error" not in rv else None,
        "drafts": drafts.list_drafts(s["name"])["history"],
        "new_nearby": {"as_of": asof, "same_category": sum(1 for x in newbies if x["category"] == s["category"]), "stores": newbies},
    }


@app.post("/api/report")
def api_report(body: dict):
    """사용자 신고: '문 닫았어요' 등. 신고된 가게는 추천에서 빠진다 (가게당 같은 종류 신고는 하루 20건까지)."""
    import sqlite3
    sid, kind = body.get("store_id"), str(body.get("kind") or "closed")
    if not isinstance(sid, int) or kind not in ("closed", "renamed", "wrong_location"):
        raise HTTPException(400, "store_id(숫자)와 kind(closed|renamed|wrong_location)가 필요합니다.")
    if not db.rows("SELECT 1 FROM stores WHERE store_id=?", [sid]):
        raise HTTPException(404, "가게 없음")
    note = str(body.get("note") or "")[:200]
    with sqlite3.connect(db.DB_PATH, timeout=30) as con:
        con.execute("CREATE TABLE IF NOT EXISTS store_reports (store_id INTEGER, kind TEXT, note TEXT, created_at TEXT)")
        n = con.execute("SELECT count(*) FROM store_reports WHERE store_id=? AND kind=? AND created_at >= date('now')", [sid, kind]).fetchone()[0]
        if n < 20:
            con.execute("INSERT INTO store_reports VALUES (?,?,?,datetime('now'))", [sid, kind, note])
    return {"ok": True, "message": "알려 주셔서 고마워요. 확인 전까지 추천에서 빼 둘게요." if kind == "closed" else "알려 주셔서 고마워요."}


@app.get("/api/regions")
def api_regions():
    """화면의 동네 선택용: 가게가 많은 읍면동 순."""
    rows = db.rows("SELECT city, emd, count(*) n FROM stores WHERE status LIKE '영업%' AND emd IS NOT NULL "
                   "GROUP BY 1, 2 ORDER BY n DESC")
    return {"regions": [{"city": r["city"], "name": r["emd"], "stores": r["n"]} for r in rows]}


@app.get("/api/balance")
def api_balance(region: str):
    return _ok(insight.resident_balance(region))


# 웹 화면 (API 경로보다 뒤에 붙여야 /api/* 가 먼저 처리된다)
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "static", html=True), name="web")
