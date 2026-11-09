"""지역 매핑, 도구, Agent 루프 테스트. 실행: python -m pytest -q

Agent 루프는 가짜 Claude 클라이언트로 검사하므로 API 키 없이 돈다.
도구 테스트는 data/processed/jeju.db 가 있어야 한다.
"""
import asyncio
from types import SimpleNamespace as NS

import pytest

from app.agent import loop, tools
from app.data import db, regions
from app.tools import insight, stores

needs_db = pytest.mark.skipif(not db.DB_PATH.exists(), reason="jeju.db 없음")


# ---------- 지역 ----------

@pytest.mark.parametrize("q,label,admin", [
    ("애월", "애월읍", ["애월읍"]),
    ("이도이동", "이도이동", ["이도2동"]),
    ("서귀동", "서귀동", ["송산동", "정방동", "중앙동", "천지동"]),
    ("서귀포시 월평동", "월평동", ["대천동"]),
    ("제주시 월평동", "월평동", ["아라동"]),
])
def test_resolve(q, label, admin):
    r = regions.resolve(q)
    assert r["label"] == label and r["admin"] == admin


def test_resolve_unknown():
    assert regions.resolve("부산") is None


def test_every_legal_dong_maps_to_admin():
    for (city, legal), admins in regions.LEGAL_TO_ADMIN.items():
        assert admins, (city, legal)


# ---------- 도구 ----------

@needs_db
def test_every_open_store_has_admin_area():
    n = db.rows("SELECT count(*) n FROM stores WHERE status LIKE '영업%' AND admin_emd IS NULL")[0]["n"]
    assert n == 0


@needs_db
def test_find_store_exact_name_first():
    m = stores.find_store("자매국수")["matches"]
    assert m[0]["name"] == "자매국수" and m[0]["match_score"] == 100


@needs_db
def test_find_store_short_names_do_not_win():
    m = stores.find_store("거멍국수")["matches"]
    assert all(x["name"] != "수" or x["match_score"] < 90 for x in m)


@needs_db
def test_search_stores_filters():
    out = stores.search_stores("애월", "카페", opened_after="2025-01-01", limit=5)
    assert out["total"] > 0
    assert all(s["open_date"] >= "2025-01-01" for s in out["stores"])
    assert all("애월읍" in s["region"] for s in out["stores"])


@needs_db
def test_crowd_levels_and_sources():
    out = insight.predict_crowd("애월", "토요일")
    assert len(out["forecast"]) == 5 and out["forecast"][4]["time_slot"] == "밤 21~24시"
    assert {f["level"] for f in out["forecast"]} <= set(insight.LEVELS)
    assert out["sources"]


@needs_db
def test_crowd_level_distribution():
    lo, hi = insight._crowd_thresholds()
    assert 0 < lo < hi


@needs_db
def test_balance_and_insight():
    b = insight.resident_balance("중문")
    assert b["level"] in ("과밀", "주의", "여유")
    a = insight.area_insight("연동")
    assert a["stores"]["open"] > 0 and sum(int(v[:-1]) for v in a["population_mix"].values()) in (99, 100, 101)


def test_unknown_region_is_error_not_exception():
    assert "error" in insight.predict_crowd("부산")


@pytest.mark.parametrize("name,args,ok", [
    ("predict_crowd", {"region": "애월"}, True),
    ("predict_crowd", {}, False),
    ("predict_crowd", {"region": 3}, False),
    ("search_stores", {"limit": True}, False),
    ("search_stores", {"zzz": 1}, False),
    ("nope", {}, False),
])
def test_validate(name, args, ok):
    assert (tools.validate(name, args) is None) == ok


# ---------- Agent 루프 (가짜 Claude) ----------

class FakeStream:
    def __init__(self, msg):
        self.msg = msg

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def __aiter__(self):
        async def gen():
            for b in self.msg.content:
                if b.type == "text":
                    yield NS(type="text", text=b.text)
        return gen()

    async def get_final_message(self):
        if not hasattr(self.msg, "usage"):
            self.msg.usage = NS(input_tokens=100, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return self.msg


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.beta = NS(messages=NS(stream=self._stream))

    def _stream(self, **kw):
        self.calls.append({**kw, "messages": list(kw["messages"])})  # 호출 시점 기록
        return FakeStream(self.replies.pop(0))


def _run(session, text):
    async def go():
        return [ev async for ev in loop.run(session, text)]
    return asyncio.run(go())


@needs_db
def test_agent_loop_calls_tool_then_answers(monkeypatch):
    fake = FakeClient([
        NS(stop_reason="tool_use", content=[
            NS(type="text", text="확인해 볼게요. "),
            NS(type="tool_use", id="t1", name="predict_crowd", input={"region": "애월", "weekday": "토요일"}),
        ]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="토요일 밤이 가장 한산해요.")]),
    ])
    monkeypatch.setattr(loop, "_client", fake)
    s = loop.Session(mode="tourist")
    evs = _run(s, "애월 토요일 언제 덜 붐벼?")

    kinds = [e["type"] for e in evs if e["type"] != "usage"]
    assert [e for e in evs if e["type"] == "usage"][0]["usd"] > 0
    assert kinds == ["text", "tool_call", "tool_result", "text", "done"]
    tr = [e for e in evs if e["type"] == "tool_result"][0]
    assert tr["is_error"] is False and tr["result"]["region"] == "애월읍"
    # 기록: user, system(유형), assistant(tool_use), user(tool_result), assistant
    assert [m["role"] for m in s.messages] == ["user", "system", "assistant", "user", "assistant"]
    assert s.messages[3]["content"][0]["tool_use_id"] == "t1"
    # 두 번째 요청은 도구 결과를 포함한 전체 기록을 보낸다
    assert len(fake.calls[1]["messages"]) == 4
    assert fake.calls[0]["model"] == (loop.MODEL_BY_MODE.get("tourist") or loop.MODEL)  # 관광객은 유형별 모델


def test_agent_loop_bad_tool_input_returns_error_result(monkeypatch):
    fake = FakeClient([
        NS(stop_reason="tool_use", content=[NS(type="tool_use", id="t1", name="predict_crowd", input={"weekday": "토"})]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="지역을 알려 주세요.")]),
    ])
    monkeypatch.setattr(loop, "_client", fake)
    evs = _run(loop.Session(), "언제 한산해?")
    res = [e for e in evs if e["type"] == "tool_result"][0]
    assert res["is_error"] and "region" in res["result"]["error"]


# ---------- 리뷰 ----------

@pytest.mark.parametrize("text,stars,expected", [
    ("대체적으로 음식이 짜고.불친절함", 1, {"맛": -1, "친절": -1}),
    ("미역국은 짜지않고 깊은맛이 나서 좋았어요", 5, {"맛": 1}),
    ("성게국수는 가성비가 떨어지네요", 4, {"가격": -1}),
    ("리뷰가 많아서 궁금했다", 3, {}),
    ("주차장이 넓어 좋았어요", 5, {"주차": 1, "분위기": 1}),
])
def test_review_classify(text, stars, expected):
    from app.tools.reviews import classify
    assert classify(text, stars) == expected


@needs_db
def test_analyze_reviews_has_no_author_info():
    from app.tools.reviews import analyze_reviews
    out = analyze_reviews("거멍국수")
    assert out["store"] == "거멍국수" and out["strengths"] and out["complaints"]
    cols = {r["name"] for r in db.rows("PRAGMA table_info(reviews)")}
    assert not cols & {"name", "level", "review", "photo", "imeges"}


# ---------- 초안·승인 (임시 DB) ----------

CLAIMS = [{"text": "국물이 진한 고기국수", "evidence": ["E3"]}]

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    (tmp_path / "t.db").touch()


def test_draft_cannot_be_approved_in_same_turn(temp_db):
    from app.tools import drafts
    ctx = {"session_id": "s1", "user_turn": 1}
    d = drafts.save_draft("자매국수", "promo", "국물이 진한 고기국수", claims=CLAIMS, _ctx=ctx)
    blocked = drafts.decide_draft(d["draft_id"], "approve", _ctx=ctx)
    assert blocked.get("blocked_by") == "human_approval_required"
    ok = drafts.decide_draft(d["draft_id"], "approve", _ctx={"session_id": "s1", "user_turn": 2})
    assert ok["status"] == "approved"


def test_new_approval_supersedes_old(temp_db):
    from app.tools import drafts
    for turn, body in ((1, "v1"), (3, "v2")):
        d = drafts.save_draft("자매국수", "promo", body, claims=CLAIMS, _ctx={"session_id": "s", "user_turn": turn})
        drafts.decide_draft(d["draft_id"], "approve", _ctx={"session_id": "s", "user_turn": turn + 1})
    h = drafts.list_drafts("자매국수")["history"]
    assert [(x["body"], x["status"]) for x in h] == [("v2", "approved"), ("v1", "superseded")]


def test_menu_price_must_be_int(temp_db):
    from app.tools import drafts
    bad = drafts.save_draft("자매국수", "menu", "메뉴", items=[{"name": "고기국수", "price": -1}])
    assert "error" in bad


def test_validate_nested_items():
    ok = {"store_name": "a", "kind": "menu", "body": "b", "items": [{"name": "고기국수", "price": 9000}]}
    assert tools.validate("save_draft", ok) is None
    assert tools.validate("save_draft", {**ok, "items": [{"price": 9000}]})
    assert tools.validate("save_draft", {**ok, "kind": "poster"})


# ---------- 네이버 등록 판별 (네트워크 없이 판별 로직만) ----------

def test_naver_address_keys():
    from app.tools import naver
    assert naver.road_key("제주특별자치도 제주시 항골남길 46, 1층 (이호일동)") == "항골남길46"
    assert naver.road_key("제주특별자치도 제주시 애월읍 하광로 490 8") == "하광로490"
    assert naver.jibun_key("제주특별자치도 제주시 이호일동 651-3") == "이호일동651-3"
    assert naver.jibun_key("제주특별자치도 제주시 애월읍 애월리 123") == "애월리123"


@pytest.mark.parametrize("name,base", [
    ("자담치킨애월점1", "자담치킨"),
    ("보배쌤보리김치와게장제주공항점", "보배쌤보리김치와게장"),
    ("자매국수", "자매국수"),
    ("고집돌우럭중문점", "고집돌우럭"),
])
def test_naver_base_name(name, base):
    from app.tools import naver
    assert naver.base_name(name) == base


def test_naver_judge():
    from app.tools import naver
    store = {"name": "하늘만큼땅만큼", "addr_road": "제주특별자치도 제주시 애월읍 애월해안로 926", "addr_jibun": None}
    same = {"title": "하늘만큼 땅만큼", "roadAddress": "제주특별자치도 제주시 애월읍 애월해안로 926", "address": ""}
    other = {"title": "하늘만큼 땅만큼 펜션", "roadAddress": "제주특별자치도 제주시 애월읍 가문동상4길 5", "address": ""}
    assert naver.judge(store, [same])["status"] == 1
    assert naver.judge(store, [other])["status"] == 2
    assert naver.judge(store, [])["status"] == 0
    assert naver._coord("1264591844") == pytest.approx(126.4591844)


# ---------- 카드 이미지 (임시 DB, Playwright 필요) ----------

def test_render_card_preview_then_final(temp_db, tmp_path, monkeypatch):
    pytest.importorskip("playwright")
    from app.tools import cards, drafts
    monkeypatch.setattr(cards, "OUT", tmp_path / "cards")
    d = drafts.save_draft("테스트국수", "menu", "설명", items=[{"name": "고기국수", "price": 10000}],
                          _ctx={"session_id": "s", "user_turn": 1})
    pre = cards.render_card(d["draft_id"])
    assert pre["preview_only"] and (tmp_path / "cards" / f"{d['draft_id']}_menu_pending.png").exists()
    drafts.decide_draft(d["draft_id"], "approve", _ctx={"session_id": "s", "user_turn": 2})
    final = cards.render_card(d["draft_id"])
    assert not final["preview_only"] and final["image"].endswith("_menu_approved.png")


def test_card_html_has_exact_prices():
    from app.tools import cards
    html = cards.build_html({"kind": "menu", "store_name": "가게", "status": "pending", "title": "", "body": "",
                             "items": [{"name": "돔베고기", "price": 18000}], "store_id": None})
    assert "18,000" in html and "돔베고기" in html and "미리보기" in html


def test_promo_requires_evidence_per_sentence(temp_db):
    from app.tools import drafts
    assert "error" in drafts.save_draft("가게", "promo", "맛있어요")
    assert "error" in drafts.save_draft("가게", "promo", "맛있어요", claims=[{"text": "맛있어요", "evidence": []}])
    assert "error" in drafts.save_draft("가게", "promo", "맛있어요", claims=[{"text": "맛있어요", "evidence": ["느낌"]}])
    ok = drafts.save_draft("가게", "promo", "맛있어요", claims=[{"text": "맛있어요", "evidence": ["E3", "사장님 말씀"]}])
    assert ok["status"] == "pending"


def test_banned_superlatives_blocked(temp_db):
    from app.tools import drafts
    out = drafts.save_draft("가게", "promo", "제주 최고 맛집", claims=[{"text": "제주 최고 맛집", "evidence": ["사장님 말씀"]}])
    assert out.get("blocked_by") == "unsupported_claim"


# ---------- 마케팅 브리프·생성 배경 ----------

@needs_db
def test_marketing_brief_has_evidence_ids():
    from app.tools.marketing import marketing_brief
    sid = db.rows("SELECT store_id FROM stores WHERE name='고이정' AND status LIKE '영업%'")[0]["store_id"]
    b = marketing_brief(sid)
    ids = {e["id"] for e in b["evidence"]}
    assert b["target_candidates"] and b["posting_timing"] and b["message_materials"]
    for group in ("target_candidates", "posting_timing"):
        assert all(x["evidence"] in ids for x in b[group])
    assert not any("밤" in e["fact"] and "한산" in e["fact"] for e in b["evidence"])  # 문 닫는 시간은 추천 안 함


def test_generate_background_without_key_is_error(temp_db, monkeypatch):
    from app.tools import drafts, imagegen
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    d = drafts.save_draft("가게", "promo", "본문", claims=[{"text": "본문", "evidence": ["사장님 말씀"]}])
    out = imagegen.generate_background(d["draft_id"], "제주 바다")
    assert "error" in out and "GEMINI_API_KEY" in out["error"]
    assert "error" in imagegen.generate_background(d["draft_id"], "제주 바다", format="poster")


# ---------- 의사결정 모델: 수요 예측, 다기준 추천 ----------

@needs_db
def test_demand_model_beats_weekday_average():
    from app.tools import forecast
    m = forecast.metrics()
    if not m:
        pytest.skip("scripts/train_demand.py 먼저 실행")
    assert m["mape"]["model"] < m["mape"]["weekday_average"]
    assert m["level_accuracy"]["model"] > m["level_accuracy"]["weekday_average"]


@needs_db
def test_crowd_with_date_uses_model_or_holiday_rule():
    r = insight.predict_crowd("애월", "11월 14일", "점심")
    assert r["date"].endswith("-11-14") and r["forecast"][0]["weekday"] == "토요일"
    h = insight.predict_crowd("애월", "2026-12-25", "점심")
    assert h["forecast"][0]["weekday"] == "일요일" and "공휴일" in h["day_outlook"]


@needs_db
def test_recommender_is_deterministic_and_explained():
    from app.tools.recommend import recommend_stores
    a = recommend_stores("애월, 한림", "한식", "토요일", "점심", limit=5)
    b = recommend_stores("애월, 한림", "한식", "토요일", "점심", limit=5)
    assert [x["store_id"] for x in a["recommendations"]] == [x["store_id"] for x in b["recommendations"]]
    top = a["recommendations"][0]
    assert abs(sum(top["score_parts"].values()) - top["score"]) < 0.01
    assert abs(sum(a["weights"].values()) - 1) < 0.01


def test_recommender_priority_shifts_weight():
    from app.tools.recommend import _weights
    assert _weights("숨은 가게")["hidden"] > _weights("")["hidden"]
