"""초안·승인 도구: save_draft, decide_draft, list_drafts.

Agent는 홍보 문구·메뉴판·안내문을 '초안(pending)'으로만 저장할 수 있다.
확정(approved)·반려(rejected)는 초안을 보여준 뒤 사용자가 새로 답한 차례에서만 가능하다.
(같은 차례에서 만들고 바로 승인하는 것을 코드로 막는다 → Agent 혼자 확정 불가)

같은 가게·같은 종류의 이전 확정본은 superseded로 바뀌어 변경 이력이 남는다.
"""
import json
import re
from datetime import datetime

from app.data import db

KINDS = {"promo": "홍보 문구", "menu": "메뉴판", "notice": "안내문"}
# 근거 없이 쓰면 안 되는 최상급·순위 표현 (표시광고 위험)
BANNED = ["최고", "1위", "일등", "넘버원", "No.1", "유일", "제일 맛있", "가장 맛있", "원조", "전국 최초"]
EVIDENCE_RE = re.compile(r"^(E\d+|사장님 말씀|사진)$")

DDL = """
CREATE TABLE IF NOT EXISTS drafts (
    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name TEXT NOT NULL,
    store_id INTEGER,
    kind TEXT NOT NULL,
    title TEXT,
    body TEXT,
    items TEXT,
    based_on TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    session_id TEXT,
    created_turn INTEGER,
    created_at TEXT,
    decided_at TEXT,
    decision_note TEXT,
    claims TEXT,
    photo TEXT,
    backgrounds TEXT
)
"""
# 예전에 만든 drafts 테이블에 새 컬럼 추가
NEW_COLS = {"claims": "TEXT", "photo": "TEXT", "backgrounds": "TEXT"}


def _con():
    con = db.connect()
    con.execute(DDL)
    have = {r[1] for r in con.execute("PRAGMA table_info(drafts)")}
    for col, typ in NEW_COLS.items():
        if col not in have:
            con.execute(f"ALTER TABLE drafts ADD COLUMN {col} {typ}")
    return con


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _public(r: dict) -> dict:
    r = dict(r)
    r["items"] = json.loads(r["items"]) if r.get("items") else []
    r["claims"] = json.loads(r["claims"]) if r.get("claims") else []
    r["backgrounds"] = json.loads(r["backgrounds"]) if r.get("backgrounds") else {}
    r["kind_label"] = KINDS.get(r["kind"], r["kind"])
    for k in ("session_id", "created_turn"):
        r.pop(k, None)
    return r


def save_draft(store_name: str, kind: str, body: str, title: str = "", items: list | None = None,
               based_on: str = "", store_id: int | None = None, claims: list | None = None,
               photo: str = "", _ctx: dict | None = None) -> dict:
    """초안 저장. 확정은 사용자 확인 뒤 decide_draft로."""
    if kind not in KINDS:
        return {"error": f"kind는 {list(KINDS)} 중 하나"}
    items = items or []
    claims = claims or []
    text = f"{title} {body}"
    banned = [w for w in BANNED if w.lower() in text.lower()]
    if banned:
        return {"error": f"근거 없는 최상급·순위 표현 {banned} 은 쓸 수 없음. 데이터로 확인된 사실로 바꿀 것.",
                "blocked_by": "unsupported_claim"}
    if kind in ("promo", "notice"):
        if not claims:
            return {"error": "홍보 문구·안내문은 claims가 필요함: 문장마다 [{text, evidence}] (evidence는 E번호·'사장님 말씀'·'사진')"}
        for c in claims:
            ev = c.get("evidence") or []
            ev = [ev] if isinstance(ev, str) else ev
            if not ev or not all(EVIDENCE_RE.match(str(e)) for e in ev):
                return {"error": f"'{c.get('text', '')}' 문장의 근거가 없거나 형식이 틀림 (E번호·'사장님 말씀'·'사진')"}
    if photo and not (db.ROOT / "data/output/uploads" / photo).exists():
        return {"error": f"첨부 사진 '{photo}' 없음. 사용자가 보낸 사진의 ID를 그대로 쓸 것."}
    for it in items:
        if not isinstance(it, dict) or not str(it.get("name", "")).strip():
            return {"error": "items는 [{name, price, note}] 형식 (name 필수)"}
        if "price" in it and not (isinstance(it["price"], int) and it["price"] >= 0):
            return {"error": f"'{it['name']}' 가격은 0 이상의 정수(원)로"}
    ctx = _ctx or {}
    with _con() as con:
        cur = con.execute(
            "INSERT INTO drafts (store_name, store_id, kind, title, body, items, based_on, session_id, created_turn, created_at, claims, photo) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [store_name, store_id, kind, title, body, json.dumps(items, ensure_ascii=False), based_on,
             ctx.get("session_id"), ctx.get("user_turn"), _now(), json.dumps(claims, ensure_ascii=False), photo or None],
        )
        draft_id = cur.lastrowid
    return {
        "draft_id": draft_id,
        "status": "pending",
        "next_step": "사장님께 초안 내용을 그대로 보여 드리고 확정할지 여쭤볼 것. 답을 받은 뒤 decide_draft 호출.",
    }


def decide_draft(draft_id: int, decision: str, note: str = "", _ctx: dict | None = None) -> dict:
    """사용자가 확정/반려를 말한 뒤에만 호출. decision: approve | reject"""
    if decision not in ("approve", "reject"):
        return {"error": "decision은 approve 또는 reject"}
    ctx = _ctx or {}
    with _con() as con:
        r = con.execute("SELECT * FROM drafts WHERE draft_id = ?", [draft_id]).fetchone()
        if not r:
            return {"error": f"초안 {draft_id} 없음"}
        if r["status"] != "pending":
            return {"error": f"초안 {draft_id}는 이미 {r['status']} 상태"}
        if r["session_id"] == ctx.get("session_id") and r["created_turn"] == ctx.get("user_turn"):
            return {
                "error": "초안을 만든 같은 차례에서는 확정·반려할 수 없음. 사장님께 초안을 보여 드리고 답을 기다릴 것.",
                "blocked_by": "human_approval_required",
            }
        status = "approved" if decision == "approve" else "rejected"
        if status == "approved":
            con.execute(
                "UPDATE drafts SET status='superseded' WHERE store_name=? AND kind=? AND status='approved'",
                [r["store_name"], r["kind"]],
            )
        con.execute(
            "UPDATE drafts SET status=?, decided_at=?, decision_note=? WHERE draft_id=?",
            [status, _now(), note, draft_id],
        )
    return {"draft_id": draft_id, "status": status, "kind": KINDS[r["kind"]], "store_name": r["store_name"]}


def list_drafts(store_name: str, kind: str = "") -> dict:
    """가게의 초안·확정본 변경 이력 (최신순)."""
    sql = "SELECT * FROM drafts WHERE store_name = ?"
    params = [store_name]
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    with _con() as con:
        rows = [dict(r) for r in con.execute(sql + " ORDER BY draft_id DESC LIMIT 20", params)]
    return {"store_name": store_name, "history": [_public(r) for r in rows]}


def set_background(draft_id: int, fmt: str, path: str):
    """generate_background가 만든 배경 이미지를 초안에 연결 (형식별 1장)."""
    with _con() as con:
        r = con.execute("SELECT backgrounds FROM drafts WHERE draft_id=?", [draft_id]).fetchone()
        bgs = json.loads(r["backgrounds"]) if r and r["backgrounds"] else {}
        bgs[fmt] = path
        con.execute("UPDATE drafts SET backgrounds=? WHERE draft_id=?", [json.dumps(bgs, ensure_ascii=False), draft_id])


def get(draft_id: int) -> dict | None:
    with _con() as con:
        r = con.execute("SELECT * FROM drafts WHERE draft_id=?", [draft_id]).fetchone()
    return _public(r) if r else None
