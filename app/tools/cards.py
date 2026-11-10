"""메뉴판·홍보 카드 이미지 생성: render_card.

AI 이미지 생성이 아니라 HTML 템플릿에 가게 정보·메뉴·가격을 넣고 브라우저 엔진(Playwright)으로 PNG를 찍는다.
→ 한글·가격이 항상 정확하고, 같은 입력이면 같은 이미지 (재현 가능).

- 확정 전 초안: '미리보기 · 사장님 확인 전' 워터마크
- 확정된 초안: 워터마크 없는 최종본
결과: data/output/cards/<draft_id>_<kind>_<status>.png
"""
import base64
import io
import re
import urllib.parse
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.data import db
from app.tools import drafts

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
OUT = db.ROOT / "data/output/cards"
SIZES = {"feed": (1080, 1080), "story": (1080, 1920), "menu": (1080, 1350)}
UPLOADS = db.ROOT / "data/output/uploads"


def _data_uri(path: Path) -> str | None:
    """로컬 이미지 → data URI (템플릿에 바로 넣기 위해)."""
    if not path or not path.exists():
        return None
    mime = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(path.suffix.lower(), "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()

_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))


def _qr(text: str) -> str | None:
    try:
        import qrcode
    except ImportError:
        return None
    img = qrcode.make(text, border=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _store_info(d: dict) -> tuple[str, str]:
    """(지역, 주소) — store_id가 있으면 인허가 DB에서, 없으면 빈 값."""
    if not d.get("store_id"):
        return "", ""
    r = db.rows("SELECT city, emd, addr_road, addr_jibun FROM stores WHERE store_id=?", [d["store_id"]])
    if not r:
        return "", ""
    r = r[0]
    addr = (r["addr_road"] or r["addr_jibun"] or "").replace("제주특별자치도 ", "")
    addr = addr.split(",")[0]  # 층·호수는 뺀다
    return (r["emd"] or r["city"] or ""), addr


def build_html(d: dict, fmt: str = "feed") -> str:
    region, address = _store_info(d)
    bg_rel = (d.get("backgrounds") or {}).get(fmt)
    bg = _data_uri(db.ROOT / bg_rel) if bg_rel else None
    photo = _data_uri(UPLOADS / d["photo"]) if d.get("photo") else None
    watermark = d["status"] != "approved"
    status_label = "사장님 확인 완료" if not watermark else "미리보기"
    if d["kind"] in ("menu", "today"):
        items = d["items"]
        n = len(items)
        two_col = n > 9
        per_col = (n + 1) // 2 if two_col else n
        item_size = 52 if per_col <= 6 else 44 if per_col <= 8 else 38 if per_col <= 10 else 32
        eyebrow = "TODAY · 오늘의 메뉴" if d["kind"] == "today" else "MENU · 차림표"
        title, body = d.get("title") or "", d.get("body") or ""
        # 위 머리글·메뉴 목록과 같은 말이면 다시 쓰지 않는다
        if re.sub(r"\s", "", title) in re.sub(r"\s", "", eyebrow) + "메뉴판차림표":
            title = ""
        rest = body
        for i in items:
            rest = rest.replace(i["name"], "")
            if i.get("price") is not None:
                rest = rest.replace(f"{i['price']:,}", "").replace(str(i["price"]), "")
        if not re.search(r"[가-힣A-Za-z]{2,}", rest.replace("원", "")):
            body = ""
        return _env.get_template("menu.html").render(
            eyebrow=eyebrow, store_name=d["store_name"], title=title, body=body,
            items=[{"name": i["name"], "price": i.get("price"), "note": i.get("note")} for i in items],
            two_col=two_col, item_size=item_size, row_pad=max(10, 30 - per_col * 2),
            title_size=84 if len(d["store_name"]) <= 8 else 66,
            address=address, status_label=status_label, watermark=watermark, bg=bg,
        )
    title = d.get("title") or d["store_name"]
    body = d.get("body") or ""
    query = urllib.parse.quote(f"{d['store_name']} {region}".strip())
    w, h = SIZES[fmt]
    story = fmt == "story"
    compact = bool(photo) and not story  # 정사각에 사진까지 들어가면 글자를 줄인다
    return _env.get_template("promo.html").render(
        w=w, h=h, story=story, pad=60 if story else 44,
        store_name=d["store_name"], title=title, body=body,
        region=("안내" if d["kind"] == "notice" else region),
        title_size=(84 if len(title) <= 14 else 68 if len(title) <= 24 else 56) - (16 if compact else 0),
        body_size=(40 if len(body) <= 80 else 34 if len(body) <= 140 else 28) - (6 if compact else 0),
        address=address, qr=_qr(f"https://map.naver.com/p/search/{query}"), watermark=watermark,
        bg=bg, photo=photo,
    )


def render_card(draft_id: int, format: str = "") -> dict:
    """초안(draft_id)을 PNG로 만든다. format: feed(1080×1080) | story(1080×1920), 메뉴판은 자동 menu(1080×1350).
    확정 전이면 미리보기 워터마크, generate_background로 만든 배경이 있으면 깔고, 사장님 사진이 있으면 넣는다."""
    hist = db.rows("SELECT * FROM drafts WHERE draft_id=?", [draft_id]) if _has_drafts() else []
    if not hist:
        return {"error": f"초안 {draft_id} 없음. save_draft로 먼저 초안을 만들 것."}
    d = drafts._public(hist[0])
    if d["status"] in ("rejected", "superseded"):
        return {"error": f"초안 {draft_id}는 {d['status']} 상태라 이미지를 만들지 않음"}
    if d["kind"] in ("menu", "today") and not d["items"]:
        return {"error": "메뉴판 초안에 메뉴(items)가 없음"}

    from playwright.sync_api import sync_playwright

    fmt = "menu" if d["kind"] in ("menu", "today") else (format or "feed")
    if fmt not in SIZES or (d["kind"] not in ("menu", "today") and fmt == "menu"):
        return {"error": "홍보 카드 format은 feed 또는 story"}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{draft_id}_{fmt}_{d['status']}.png"
    w, h = SIZES[fmt]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        page.set_content(build_html(d, fmt), wait_until="load")
        page.screenshot(path=str(path), full_page=False)
        browser.close()
    return {
        "draft_id": draft_id,
        "format": fmt,
        "image": _show(path),
        "uses_ai_background": bool((d.get("backgrounds") or {}).get(fmt)),
        "uses_owner_photo": bool(d.get("photo")),
        "status": d["status"],
        "preview_only": d["status"] != "approved",
        "note": "확정 전 미리보기 (워터마크 있음). 사장님이 확정하면 decide_draft 후 다시 render_card로 최종본을 만든다."
        if d["status"] != "approved" else "확정된 최종본",
    }


def _show(path: Path) -> str:
    try:
        return path.relative_to(db.ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _has_drafts() -> bool:
    return bool(db.rows("SELECT 1 FROM sqlite_master WHERE name='drafts'"))
