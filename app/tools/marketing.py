"""마케팅 브리프: marketing_brief.

가게 하나에 대해 마케팅 절차의 앞 단계(진단 → 타깃 → 메시지 재료 → 게시 시점)를 데이터로 정리한다.
모든 사실에 근거 번호(E1, E2 …)를 붙인다. 홍보 문구 초안(save_draft)은 문장마다 이 번호나
'사장님 말씀'을 근거로 달아야 저장된다 → 데이터에 없는 홍보 표현을 막는다.
"""
from app.data import db
from app.tools import insight, naver, reviews

# 인허가 업태 → 카드 업종(1048)
CATEGORY_TO_BIZ = {
    "한식": "한식 음식점업", "식육(숯불구이)": "한식 음식점업", "탕류(보신용)": "한식 음식점업", "냉면집": "한식 음식점업",
    "횟집": "한식 음식점업", "분식": "한식 음식점업", "김밥(도시락)": "한식 음식점업",
    "중국식": "중식 음식점업", "일식": "일식 음식점업", "복어취급": "일식 음식점업",
    "경양식": "서양식 음식점업", "패밀리레스트랑": "서양식 음식점업",
    "외국음식전문점(인도,태국등)": "기타 외국식 음식점업",
    "패스트푸드": "피자 햄버거 샌드위치 및 유사 음식점업",
    "호프/통닭": "기타 주점업", "정종/대포집/소주방": "기타 주점업", "통닭(치킨)": "기타 주점업",
}


class _Evidence:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, fact: str, source: str) -> str:
        eid = f"E{len(self.items) + 1}"
        self.items.append({"id": eid, "fact": fact, "source": source})
        return eid


def marketing_brief(store_id: int) -> dict:
    """가게 마케팅 브리프: 진단·손님층·타깃 후보·게시 시점·메시지 재료, 근거 번호 포함."""
    rows = db.rows("SELECT * FROM stores WHERE store_id=?", [store_id])
    if not rows:
        return {"error": f"store_id {store_id} 없음. find_store로 먼저 찾을 것."}
    s = rows[0]
    region = s["emd"]
    ev = _Evidence()
    diagnosis, targets, timing, messages, cautions = [], [], [], [], []

    # 1. 진단: 가게 기본·네이버 등록
    ev_open = ev.add(f"{s['name']}: {s['category']}, {s['open_date']} 인허가, {s['city']} {s['emd']}", "780 음식점 인허가")
    diagnosis.append({"point": "가게 기본 정보", "evidence": ev_open})
    nv = naver.check_naver_listed(store_id)
    if "error" not in nv:
        e = ev.add(f"네이버 지도: {nv['naver_status']}", "네이버 지역 검색")
        diagnosis.append({"point": f"네이버 지도 {nv['naver_status']}", "evidence": e,
                          "action": "스마트플레이스 등록부터 권장" if nv["naver_status"] == "미등록 후보" else ""})

    # 2. 리뷰 (있을 때만)
    rv = reviews.analyze_reviews(s["name"])
    has_reviews = "error" not in rv and rv.get("store")
    if has_reviews:
        for st in rv["strengths"][:3]:
            e = ev.add(f"리뷰 강점 '{st['factor']}' {st['count']}건(글 리뷰의 {st['share_of_text_reviews']}), 예: {' / '.join(st['examples'])}",
                       "903 구글 리뷰(2021)")
            messages.append({"angle": f"{st['factor']} 강점", "evidence": e})
        for c in rv["complaints"][:2]:
            e = ev.add(f"리뷰 불만 '{c['factor']}' {c['count']}건, 예: {' / '.join(c['examples'])}", "903 구글 리뷰(2021)")
            cautions.append({"point": f"{c['factor']} 불만은 홍보로 덮지 말고 개선 제안으로", "evidence": e})
        cautions.append({"point": "리뷰는 2021년 자료. 지금도 맞는지 사장님께 확인 후 사용", "evidence": None})
    else:
        messages.append({"angle": "가게 자랑거리", "evidence": None,
                         "need": "리뷰 데이터가 없음. 대표 메뉴·자랑거리를 사장님께 여쭤보고 그 말씀을 근거('사장님 말씀')로 쓸 것"})

    # 3. 손님층·타깃 후보
    area = insight.area_insight(region) if region else {"error": "지역 없음"}
    if "error" not in area:
        tw = area["tourist_weight"]
        e_mix = ev.add(f"{area['region']} 유동인구 구성 {area['population_mix']}, 방문/거주 {area['visitor_per_resident']}", "583 유동인구")
        e_vis = ev.add(f"{area['region']} 방문객 상위: {', '.join(area['top_visitor_groups'])}", "583 유동인구")
        e_day = ev.add(f"{area['region']} 방문이 가장 많은 요일: {area['busiest_day']} (요일 계수 {area['visitor_weekday_factor']})", "583 유동인구")
        if tw >= 0.3:
            targets.append({"who": "제주 여행 온 내국인 관광객", "why": "방문 인구 비중이 높은 동네", "evidence": e_mix})
        targets.append({"who": "동네 주민·직장인 단골", "why": "거주·근무 인구가 주된 동네" if tw < 0.3 else "관광 비수기 매출 버팀목", "evidence": e_mix})
        targets.append({"who": f"방문객 상위층 ({area['top_visitor_groups'][0]})", "why": "이 동네 방문객 중 가장 많은 성별·연령", "evidence": e_vis})
        timing.append({"when": f"{area['busiest_day']} 전날 저녁 ~ 당일 오전에 게시", "why": "방문이 가장 많은 요일 직전", "evidence": e_day})

        crowd = insight.predict_crowd(region)
        if "error" not in crowd:
            # 밤 21~24시는 문 닫는 가게가 많아 홍보용 '한산한 시간'에서 뺀다
            open_hours = [f for f in crowd["forecast"] if not f["time_slot"].startswith("밤")]
            quiet = [f"{q['weekday']} {q['time_slot']}" for q in sorted(open_hours, key=lambda f: f["quiet_rank"])[:3]]
            busy = [f"{f['weekday']} {f['time_slot']}" for f in crowd["forecast"] if f["level"] == "붐빔"][:3]
            e_q = ev.add(f"{area['region']} 식당이 가장 한산한 때: {', '.join(quiet)}" + (f" / 붐비는 때: {', '.join(busy)}" if busy else ""),
                         "583·490·502 혼잡 예측 (과거 패턴)")
            messages.append({"angle": "한산한 시간 방문 유도 (예: '이 시간엔 기다림 없이')", "evidence": e_q})

    # 4. 업종 손님 구성 (제주 전체)
    biz = CATEGORY_TO_BIZ.get(s["category"] or "")
    if biz:
        cust = db.rows("SELECT user_group, sum(use_amount) a FROM card_food_customer WHERE biz_nm=? GROUP BY 1", [biz])
        tot = sum(c["a"] for c in cust) or 1
        mix = ", ".join(f"{c['user_group']} {c['a'] / tot:.0%}" for c in sorted(cust, key=lambda c: -c["a"]))
        e = ev.add(f"제주 {biz} 카드 소비 구성: {mix}", "1048 업종별 카드 이용 (최근 12개월)")
        diagnosis.append({"point": "업종 손님 구성 (제주 전체)", "evidence": e})

    channels = [
        {"channel": "인스타그램 피드", "format": "feed", "size": "1080×1080", "use": "대표 메뉴·강점 한 가지"},
        {"channel": "인스타그램·카카오 스토리", "format": "story", "size": "1080×1920", "use": "오늘의 메뉴, 한산한 시간 안내"},
        {"channel": "네이버 스마트플레이스 소식/소개", "format": "feed", "size": "1080×1080", "use": "소개글 + 대표 이미지"},
        {"channel": "가게 앞·테이블", "format": "menu", "size": "1080×1350", "use": "큰 글씨 메뉴판"},
    ]
    return {
        "store": {"store_id": store_id, "name": s["name"], "category": s["category"], "region": region},
        "diagnosis": diagnosis,
        "target_candidates": targets,
        "message_materials": messages,
        "posting_timing": timing,
        "cautions": cautions,
        "channels": channels,
        "evidence": ev.items,
        "rules": [
            "홍보 문구의 모든 문장은 evidence id(E1…) 또는 '사장님 말씀'을 근거로 단다 (save_draft의 claims)",
            "근거 없는 최상급·순위 표현(최고, 1위, 유일) 금지",
            "음식 사진은 생성하지 않는다. 실제 사진은 사장님 사진만 사용, 생성형 AI는 배경에만",
        ],
        "sources": db.cite("stores", "pop_daily", "meal_time_pattern", "card_food_customer") + (db.cite("reviews") if has_reviews else []),
    }
