"""Agent가 호출할 수 있는 도구 목록 (Claude tool 정의 + 실행 함수)."""
import json
from typing import Any, Callable

from app.tools import cards, drafts, imagegen, insight, listing, marketing, naver, places, recommend, reviews, stores

REGION = {"type": "string", "description": "제주 읍·면·동 이름. 예: 애월읍, 애월, 연동, 이도2동, 서귀동, 중문"}


def _tool(name: str, description: str, props: dict, required: list[str], fn: Callable, needs_ctx: bool = False) -> dict:
    return {
        "spec": {
            "name": name,
            "description": description,
            "eager_input_streaming": True,
            "input_schema": {
                "type": "object",
                "properties": props,
                "required": required,
                "additionalProperties": False,
            },
        },
        "fn": fn,
        "needs_ctx": needs_ctx,
    }


TOOLS = [
    _tool(
        "find_store",
        "상호(오타 허용)와 주소 일부로 제주 음식점 인허가 목록에서 가게 하나를 찾는다. "
        "사장님이 자기 가게를 말하거나, 사용자가 특정 가게를 물을 때 먼저 호출. match_score가 낮거나 후보가 여럿이면 사용자에게 주소로 확인한다.",
        {
            "name": {"type": "string", "description": "가게 이름"},
            "address_hint": {"type": "string", "description": "주소나 동네 일부 (선택)"},
        },
        ["name"],
        stores.find_store,
    ),
    _tool(
        "search_stores",
        "지역·업종·개업일·네이버 미등록 여부로 영업 중인 가게 목록과 업종별 개수를 조회한다. "
        "관광객 식당 추천, 새로 문 연 가게 찾기, 미등록 가게 발굴에 사용.",
        {
            "region": REGION,
            "category": {"type": "string", "description": "업종. 예: 한식, 카페, 횟집, 고기, 술집, 분식, 양식, 중식, 일식, 디저트"},
            "opened_after": {"type": "string", "description": "이 날짜 이후 개업 (YYYY-MM-DD)"},
            "unlisted_only": {"type": "boolean", "description": "네이버 지도 미등록 후보만"},
            "keyword": {"type": "string", "description": "상호에 들어가는 단어 (예: 국수, 해장)"},
            "limit": {"type": "integer", "description": "최대 개수 (기본 20, 최대 50)"},
        },
        [],
        stores.search_stores,
    ),
    _tool(
        "area_insight",
        "지역 상권 요약: 방문객 성별·연령, 요일별 방문 패턴, 식당 시간대 비율, 가게 수·최근 개업/폐업, 제주 외식 트렌드. "
        "사장님에게 '언제, 어떤 손님이 오는지' 알려주거나 지역 분위기를 설명할 때 사용.",
        {"region": REGION},
        ["region"],
        insight.area_insight,
    ),
    _tool(
        "predict_crowd",
        "지역의 요일·시간대별 식당 혼잡 등급(한산/보통/붐빔)을 과거 패턴으로 예측한다 (실시간 아님). "
        "요일·시간대를 비우면 전체 표와 가장 한산한 시간 3개를 준다.",
        {
            "region": REGION,
            "weekday": {"type": "string", "description": "요일(예: 토요일) 또는 날짜(YYYY-MM-DD)"},
            "time_slot": {"type": "string", "description": "점심, 저녁, 오후, 밤 또는 시각(예: 12시, 오후 7시)"},
        },
        ["region"],
        insight.predict_crowd,
    ),
    _tool(
        "resident_balance",
        "지역의 거주인구 대비 방문인구 비율로 도민 생활권 과밀 여부(과밀/주의/여유)와 추천 가중치를 준다. "
        "관광객에게 추천할 지역을 고를 때 과밀 지역을 덜 추천하기 위해 사용.",
        {"region": REGION},
        ["region"],
        insight.resident_balance,
    ),
    _tool(
        "recommend_stores",
        "관광객 식당 추천 의사결정 모델. 여러 동네(쉼표 구분)의 가게를 '덜 붐빔·생활권 여유·숨은 가게(네이버 미등록)·오래된 가게' "
        "네 기준 가중 점수로 순위 매긴다. 관광객이 식당을 추천해 달라고 하면 이 도구를 먼저 쓴다. 근처 동네를 2~4곳 함께 넣으면 덜 붐비는 동네로 분산된다.",
        {
            "regions_text": {"type": "string", "description": "동네 이름들, 쉼표 구분 (예: '애월, 한림, 한경')"},
            "category": {"type": "string", "description": "업종 (예: 한식, 카페, 횟집, 고기, 해산물)"},
            "when": {"type": "string", "description": "요일 또는 날짜 (예: 토요일, 2026-11-14, 11월 14일)"},
            "time_slot": {"type": "string", "description": "점심, 저녁 등 (기본 점심)"},
            "priority": {"type": "string", "description": "더 중요하게 볼 기준: 덜 붐빔 | 생활권 여유 | 숨은 가게 | 오래된 가게"},
            "limit": {"type": "integer"},
        },
        ["regions_text"],
        recommend.recommend_stores,
    ),
    _tool(
        "plan_itinerary",
        "관광객 하루 일정: 고른 동네들의 덜 붐비는 관광 장소(오름·해수욕장·관광지·명소)와 추천 식당을 가까운 순으로 배치하고 "
        "이동 시간(직선거리 기반 추정)을 붙인다. 점심 시간대가 붐비면 점심을 당긴다.",
        {
            "regions_text": {"type": "string", "description": "동네들, 쉼표 구분 (예: '한림, 한경')"},
            "when": {"type": "string", "description": "날짜 또는 요일"},
            "start": {"type": "string", "description": "출발 시각 HH:MM (기본 10:00)"},
            "stops": {"type": "integer", "description": "관광 장소 수 (기본 3)"},
            "kinds": {"type": "string", "description": "장소 종류, 쉼표 구분: 관광지,오름,해수욕장,명소"},
            "meals": {"type": "string", "description": "점심 / 점심,저녁"},
            "category": {"type": "string", "description": "식당 업종 (선택)"},
        },
        ["regions_text"],
        places.plan_itinerary,
    ),
    _tool(
        "place_crowd",
        "관광 장소(오름·해수욕장·관광지·명소)의 그 달 혼잡 정도와 가장 한산한 달 (와이파이·관광지 유입 데이터, 월 단위).",
        {"name": {"type": "string", "description": "장소 이름 (예: 성산일출봉, 협재)"}, "when": {"type": "string"}},
        ["name"],
        places.place_crowd,
    ),
    _tool(
        "make_listing_kit",
        "네이버 지도(스마트플레이스) 등록 자료 묶음: 인허가로 채운 기본 정보, 사장님이 준비할 것, 등록 순서. "
        "미등록 후보 가게 사장님께 등록을 도와드릴 때 사용하고, 소개글은 save_draft(kind=intro)로 초안을 만든다.",
        {"store_id": {"type": "integer"}},
        ["store_id"],
        listing.make_listing_kit,
    ),
    _tool(
        "check_naver_listed",
        "가게가 네이버 지도에 등록돼 있는지 확인한다 (등록 / 확인 필요 / 미등록 후보). find_store로 얻은 store_id가 필요. "
        "미등록 후보면 사장님께 등록을 권하고 소개글·메뉴판 초안을 도와드릴 수 있다.",
        {"store_id": {"type": "integer", "description": "find_store / search_stores 결과의 store_id"}},
        ["store_id"],
        naver.check_naver_listed,
    ),
    _tool(
        "analyze_reviews",
        "가게 리뷰를 요인(맛·양·가격·친절·위생·주차·대기·분위기)별 긍정/부정으로 나누고 대표 문장을 준다. "
        "강점은 홍보 문구 재료로, 불만은 사장님께 드릴 개선 제안 재료로 쓴다. 부정 리뷰를 숨기지 않는다.",
        {"store_name": {"type": "string", "description": "가게 이름"}},
        ["store_name"],
        reviews.analyze_reviews,
    ),
    _tool(
        "marketing_brief",
        "가게 홍보를 시작할 때 먼저 호출하는 마케팅 브리프: 진단(인허가·네이버 등록), 리뷰 강점·불만, 동네 손님층, 타깃 후보, "
        "게시 시점, 메시지 재료, 채널을 정리하고 모든 사실에 근거 번호(E1…)를 붙인다. 홍보 문구는 이 근거 번호로만 쓴다.",
        {"store_id": {"type": "integer", "description": "find_store로 찾은 store_id"}},
        ["store_id"],
        marketing.marketing_brief,
    ),
    _tool(
        "save_draft",
        "홍보 문구(promo)·메뉴판(menu)·안내문(notice)을 '초안'으로 저장한다. 확정이 아니다. "
        "저장 후 초안 내용을 사장님께 그대로 보여 드리고 확정 여부를 여쭤본다. "
        "메뉴 사진에서 읽은 메뉴·가격은 반드시 이 도구로 초안을 만들어 확인받는다.",
        {
            "store_name": {"type": "string", "description": "가게 이름"},
            "kind": {"type": "string", "enum": list(drafts.KINDS), "description": "promo 홍보 | menu 메뉴판 | today 오늘의 메뉴 | notice 안내문 | intro 소개글"},
            "title": {"type": "string", "description": "제목 또는 대표 문구 (선택)"},
            "body": {"type": "string", "description": "본문. 가게 이름·주소는 카드 아래에 자동으로 들어가므로 본문에 다시 쓰지 않는다"},
            "items": {
                "type": "array",
                "description": "메뉴판일 때 메뉴 목록",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "price": {"type": "integer", "description": "원 단위 정수"},
                        "note": {"type": "string"},
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
            "based_on": {"type": "string", "description": "근거 요약 (예: 타깃 E8, 메시지 E3)"},
            "claims": {
                "type": "array",
                "description": "홍보 문구·안내문 필수. 제목·본문의 문장마다 근거: E번호(marketing_brief), '사장님 말씀', '사진'",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["text", "evidence"],
                    "additionalProperties": False,
                },
            },
            "photo": {"type": "string", "description": "사용자가 보낸 사진의 ID ([첨부 사진 ID: …]). 카드에 실제 사진으로 들어감"},
            "store_id": {"type": "integer", "description": "find_store로 찾은 store_id (선택)"},
        },
        ["store_name", "kind", "body"],
        drafts.save_draft,
        needs_ctx=True,
    ),
    _tool(
        "decide_draft",
        "사장님이 초안을 보고 '좋다/확정' 또는 '아니다/다시'라고 답한 뒤에만 호출해 초안을 확정(approve)하거나 반려(reject)한다. "
        "초안을 만든 같은 차례에서는 호출해도 막힌다.",
        {
            "draft_id": {"type": "integer"},
            "decision": {"type": "string", "enum": ["approve", "reject"]},
            "note": {"type": "string", "description": "사장님 의견 (반려 사유, 수정 요청 등)"},
        },
        ["draft_id", "decision"],
        drafts.decide_draft,
        needs_ctx=True,
    ),
    _tool(
        "render_card",
        "초안을 PNG로 만든다: 메뉴판 1080×1350, 홍보 카드 feed 1080×1080(인스타 피드·네이버) / story 1080×1920(스토리). "
        "확정 전이면 '미리보기' 워터마크, 확정 후면 최종본. 생성 배경·사장님 사진이 있으면 함께 들어간다. "
        "save_draft 직후 미리보기를 보여 드리고, decide_draft로 확정한 뒤 다시 호출해 최종본을 만든다.",
        {"draft_id": {"type": "integer"}, "format": {"type": "string", "enum": ["feed", "story"], "description": "홍보 카드 형식 (메뉴판은 무시)"}},
        ["draft_id"],
        cards.render_card,
    ),
    _tool(
        "generate_background",
        "생성형 AI(나노바나나)로 카드 배경을 만든다. 글자·음식·사람 없이 장면·분위기만. 타깃과 메시지에 맞는 제주 장면을 concept로 준다 "
        "(예: '현무암 돌담과 아침 햇살', '노을 지는 애월 바다'). 비용이 들므로 초안당 형식별 한 번만. 실패하면 배경 없이 render_card.",
        {
            "draft_id": {"type": "integer"},
            "concept": {"type": "string", "description": "배경 장면 설명 (타깃·메시지와 연결)"},
            "format": {"type": "string", "enum": ["feed", "story", "menu"]},
        },
        ["draft_id", "concept"],
        imagegen.generate_background,
    ),
    _tool(
        "list_drafts",
        "가게의 초안·확정본·이전 버전 이력을 최신순으로 본다. 기존 홍보 문구를 고칠 때 먼저 확인.",
        {
            "store_name": {"type": "string"},
            "kind": {"type": "string", "enum": list(drafts.KINDS)},
        },
        ["store_name"],
        drafts.list_drafts,
    ),
]

TOOL_SPECS = [t["spec"] for t in TOOLS]
_BY_NAME = {t["spec"]["name"]: t for t in TOOLS}
_JSON_TYPES = {"string": str, "boolean": bool, "integer": int, "number": (int, float), "array": list, "object": dict}


def _check(value, prop: dict, path: str) -> str | None:
    typ = prop["type"]
    if not isinstance(value, _JSON_TYPES[typ]) or (typ in ("integer", "number") and isinstance(value, bool)):
        return f"{path} 형식이 {typ} 아님"
    if "enum" in prop and value not in prop["enum"]:
        return f"{path} 값은 {prop['enum']} 중 하나"
    if typ == "array":
        for i, v in enumerate(value):
            err = _check(v, prop["items"], f"{path}[{i}]")
            if err:
                return err
    if typ == "object" and "properties" in prop:
        for k in prop.get("required", []):
            if k not in value:
                return f"{path}.{k} 누락"
        for k, v in value.items():
            if k not in prop["properties"]:
                return f"{path}.{k} 알 수 없는 항목"
            err = _check(v, prop["properties"][k], f"{path}.{k}")
            if err:
                return err
    return None


def validate(name: str, args: Any) -> str | None:
    """도구 입력 검사. 문제가 있으면 오류 메시지, 없으면 None.

    eager_input_streaming을 켜면 서버가 입력을 검증하지 않으므로 직접 확인한다.
    """
    t = _BY_NAME.get(name)
    if not t:
        return f"알 수 없는 도구: {name}"
    if not isinstance(args, dict):
        return "입력이 JSON 객체가 아님"
    schema = t["spec"]["input_schema"]
    for k in schema["required"]:
        if k not in args:
            return f"필수 입력 누락: {k}"
    for k, v in args.items():
        prop = schema["properties"].get(k)
        if prop is None:
            return f"알 수 없는 입력: {k}"
        err = _check(v, prop, k)
        if err:
            return err
    return None


def run(name: str, args: dict, ctx: dict | None = None) -> tuple[dict, bool]:
    """도구 실행 → (결과, 오류 여부). ctx: 세션 ID·사용자 차례 (승인 도구가 사용)."""
    err = validate(name, args)
    if err:
        return {"error": err, "input": args}, True
    t = _BY_NAME[name]
    try:
        out = t["fn"](**args, _ctx=ctx or {}) if t["needs_ctx"] else t["fn"](**args)
        return out, "error" in out
    except Exception as e:  # 도구 내부 오류는 Agent가 보고 다시 계획하도록 결과로 돌려준다
        return {"error": f"{type(e).__name__}: {e}"}, True


def to_content(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, default=str)
