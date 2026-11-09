"""생성형 배경: generate_background (Google Gemini 'Nano Banana' 이미지 모델).

원칙
  - 배경·분위기만 생성한다. 글자·음식·사람·로고는 넣지 않는다
    (글자는 템플릿이 정확히 찍고, 음식은 사장님 실제 사진만 쓴다 → 허위·과장 광고 방지)
  - 생성 이미지에는 Google SynthID 워터마크가 들어가고, 카드에 'AI 생성 배경' 표시를 한다
  - 비용 보호: 하루 생성 한도 (GEMINI_DAILY_LIMIT, 기본 30장)
"""
import base64
import os
from datetime import date, datetime

from dotenv import load_dotenv

from app.data import db
from app.tools import drafts

load_dotenv(db.ROOT / ".env")

MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-nano-banana-2.1")
DAILY_LIMIT = int(os.getenv("GEMINI_DAILY_LIMIT", "30"))
OUT = db.ROOT / "data/output/backgrounds"
ASPECT = {"feed": "1:1", "story": "9:16", "menu": "4:5"}

STYLE_RULES = (
    "Photographic background image for a small local restaurant's promotional card in Jeju Island, Korea. "
    "Absolutely no text, letters, numbers, signs, logos, watermarks, food, dishes, drinks, or people. "
    "Keep a large calm, softly blurred area with low detail where text will be placed on top. "
    "Natural light, warm and authentic, not overly saturated."
)

LOG_DDL = "CREATE TABLE IF NOT EXISTS image_log (id INTEGER PRIMARY KEY, day TEXT, draft_id INTEGER, fmt TEXT, concept TEXT, path TEXT, created_at TEXT)"


def _used_today() -> int:
    with db.connect() as con:
        con.execute(LOG_DDL)
        return con.execute("SELECT count(*) FROM image_log WHERE day=?", [date.today().isoformat()]).fetchone()[0]


def _log(draft_id: int, fmt: str, concept: str, path: str):
    with db.connect() as con:
        con.execute(LOG_DDL)
        con.execute("INSERT INTO image_log (day, draft_id, fmt, concept, path, created_at) VALUES (?,?,?,?,?,?)",
                    [date.today().isoformat(), draft_id, fmt, concept, path, datetime.now().isoformat(timespec="seconds")])


def generate_background(draft_id: int, concept: str, format: str = "feed") -> dict:
    """초안에 쓸 배경 이미지를 생성해 연결한다. concept: 타깃·메시지에 맞는 장면 (예: '제주 돌담과 아침 햇살')."""
    if format not in ASPECT:
        return {"error": f"format은 {list(ASPECT)} 중 하나"}
    d = drafts.get(draft_id)
    if not d:
        return {"error": f"초안 {draft_id} 없음"}
    if d["status"] in ("rejected", "superseded"):
        return {"error": f"초안 {draft_id}는 {d['status']} 상태"}
    if not os.getenv("GEMINI_API_KEY"):
        return {"error": "GEMINI_API_KEY 없음. 배경 없이 render_card로 기본 디자인을 쓸 것."}
    used = _used_today()
    if used >= DAILY_LIMIT:
        return {"error": f"오늘 배경 생성 한도({DAILY_LIMIT}장) 초과. 기존 배경이나 기본 디자인을 쓸 것."}

    try:
        from google import genai
        client = genai.Client()
        it = client.interactions.create(
            model=MODEL,
            input=f"{STYLE_RULES}\nScene: {concept}",
            response_format={"type": "image", "mime_type": "image/jpeg", "aspect_ratio": ASPECT[format], "image_size": "1K"},
        )
        data = base64.b64decode(it.output_image.data)
    except Exception as e:  # 한도·네트워크 오류는 Agent가 보고 기본 디자인으로 대체
        return {"error": f"배경 생성 실패 ({type(e).__name__}): {str(e)[:200]}"}

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{draft_id}_{format}_{datetime.now():%H%M%S}.jpg"
    path.write_bytes(data)
    rel = path.relative_to(db.ROOT).as_posix()
    drafts.set_background(draft_id, format, rel)
    _log(draft_id, format, concept, rel)
    return {
        "draft_id": draft_id,
        "format": format,
        "background": rel,
        "model": MODEL,
        "used_today": used + 1,
        "daily_limit": DAILY_LIMIT,
        "next_step": f"render_card(draft_id={draft_id}, format='{format}')로 글자를 얹은 카드를 만든다",
        "note": "배경만 AI 생성 (글자·음식·사람 없음). SynthID 워터마크 포함, 카드에 'AI 생성 배경' 표시",
    }
