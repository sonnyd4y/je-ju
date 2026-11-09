"""관광 장소·일정·지도 데이터: place_crowd, plan_itinerary, map_data.

일정 짜기 (규칙 기반, 같은 입력 → 같은 일정)
  1. 고른 동네들의 관광 장소 후보 → 그 달 장소 혼잡(poi_month)이 낮을수록, 종류가 겹치지 않을수록 우선
  2. 식사는 추천 의사결정 모델(recommend_stores)의 상위 가게. 지도 좌표가 있는 가게를 우선
  3. 가장 가까운 곳부터 차례로 방문 (최근접 이웃), 이동 시간 = 직선거리 × 1.3 ÷ 시속 35km (도로 경로 아님, 추정)
  4. 점심 시간대(12~15시)가 '붐빔'이면 점심을 11:30으로 당긴다
"""
import math
from datetime import datetime, timedelta

import pandas as pd

from app.data import db, regions
from app.tools import insight, recommend

STAY = {"오름": 90, "해수욕장": 90, "관광지": 90, "명소": 60, "식사": 60}
LEVEL_SCORE = {"한산": 1.0, "보통": 0.6, "붐빔": 0.2}
KIND_ICON = {"오름": "⛰", "해수욕장": "🏖", "관광지": "🏛", "명소": "📍", "식사": "🍚"}


def km(a_lat, a_lng, b_lat, b_lng) -> float:
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def travel_min(d_km: float) -> int:
    return max(5, int(round(d_km * 1.3 / 35 * 60 / 5) * 5))


def _month(when: str) -> int:
    d = insight._as_date(when)
    return pd.Timestamp(d).month if d else pd.Timestamp.today().month


def _poi_levels(month: int) -> dict[int, str]:
    try:
        return {r["poi_id"]: r["level"] for r in db.rows("SELECT poi_id, level FROM poi_month WHERE month=?", [month])}
    except Exception:
        return {}


def place_crowd(name: str, when: str = "") -> dict:
    """관광 장소(오름·해수욕장·관광지·명소)의 그 달 혼잡 정도 (와이파이·관광지 유입 데이터)."""
    from rapidfuzz import fuzz, process
    pois = db.rows("SELECT * FROM pois")
    hit = process.extractOne(name, [p["name"] for p in pois], scorer=fuzz.WRatio)
    if not hit or hit[1] < 70:
        return {"error": f"'{name}' 장소를 찾지 못함"}
    p = pois[hit[2]]
    rows = db.rows("SELECT month, factor, level, source FROM poi_month WHERE poi_id=? ORDER BY month", [p["poi_id"]])
    m = _month(when)
    cur = next((r for r in rows if r["month"] == m), None)
    return {
        "place": p["name"], "kind": p["kind"], "region": p["emd"], "month": m,
        "level": cur["level"] if cur else "정보 없음",
        "vs_usual": round(cur["factor"], 2) if cur else None,
        "by_month": {r["month"]: r["level"] for r in rows},
        "quietest_months": [r["month"] for r in sorted(rows, key=lambda r: r["factor"])[:3]],
        "note": "월 단위 과거 패턴 (시간대별 자료 없음). vs_usual은 이 장소 연평균 대비 그 달 방문 비율" if rows else "이 장소는 방문 자료가 없음",
        "sources": db.cite("wifi_monthly", "sight_monthly") if rows else [],
    }


def plan_itinerary(regions_text: str, when: str = "", start: str = "10:00", stops: int = 3,
                   kinds: str = "관광지,오름,해수욕장,명소", meals: str = "점심", category: str = "") -> dict:
    """하루 일정: 덜 붐비는 관광 장소 + 추천 식당을 가까운 순으로 배치하고 이동 시간을 붙인다."""
    names = [x.strip() for x in regions_text.replace("/", ",").split(",") if x.strip()]
    res = [regions.resolve(n) for n in names]
    res = [r for r in res if r]
    if not res:
        return {"error": "지역을 찾지 못함 (예: '한림, 한경')"}
    month = _month(when)
    levels = _poi_levels(month)
    kind_list = [k.strip() for k in kinds.split(",") if k.strip()]
    admin = [(r["city"], a) for r in res for a in r["admin"]]

    pois = db.query("SELECT * FROM pois")
    in_area = pd.Series([(c, e) in admin for c, e in zip(pois.city, pois.emd)], index=pois.index)
    pois = pois[in_area & pois.kind.isin(kind_list)]
    if pois.empty:
        return {"error": "이 동네에는 고른 종류의 관광 장소 자료가 없음"}
    pois = pois.assign(level=pois.poi_id.map(levels).fillna("정보 없음"))
    pois["score"] = pois.level.map(LEVEL_SCORE).fillna(0.6) + pois.poi_id.isin(levels.keys()) * 0.1  # 자료 있는 곳 약간 우선
    # 종류가 고르게: 종류별 상위부터 번갈아
    pois = pois.sort_values(["score", "poi_id"], ascending=[False, True])
    picked, seen = [], {}
    for _, p in pois.iterrows():
        if seen.get(p.kind, 0) < max(1, stops // len(kind_list) + 1):
            picked.append(p)
            seen[p.kind] = seen.get(p.kind, 0) + 1
        if len(picked) >= stops:
            break

    # 식사: 추천 모델 상위 중 좌표 있는 가게
    meal_list = [m.strip() for m in meals.split(",") if m.strip()]
    meal_stops = []
    for m in meal_list:
        rec = recommend.recommend_stores(",".join(names), category, when, m, limit=10, require_coords=True)
        coords = {r["store_id"]: r for r in db.rows(
            f"SELECT store_id, lat, lng FROM stores WHERE store_id IN ({','.join(str(x['store_id']) for x in rec.get('recommendations', [])) or '0'}) AND lat IS NOT NULL")}
        used = {ms["store_id"] for ms in meal_stops}
        best = next((x for x in rec.get("recommendations", []) if x["store_id"] in coords and x["store_id"] not in used), None)
        if best:
            c = coords[best["store_id"]]
            region_level = next((rg["crowd_level"] for rg in rec["regions"] if rg["region"] == best["region"]), "보통")
            meal_stops.append({"meal": m, "name": best["name"], "kind": "식사", "lat": c["lat"], "lng": c["lng"],
                               "level": region_level, "store_id": best["store_id"], "category": best["category"],
                               "naver": best["naver"], "score": best["score"]})

    # 방문 순서: 첫 동네 중심에서 가장 가까운 곳부터
    cent = db.rows("SELECT lat, lng FROM region_centroids WHERE city=? AND emd=?", [res[0]["city"], res[0]["admin"][0]])
    cur_lat, cur_lng = (cent[0]["lat"], cent[0]["lng"]) if cent else (picked[0].lat, picked[0].lng)
    todo = [{"name": p["name"], "kind": p["kind"], "lat": p.lat, "lng": p.lng, "level": p.level, "poi_id": int(p.poi_id)} for p in picked]
    t = datetime.strptime(start, "%H:%M")
    lunch = next((m for m in meal_stops if m["meal"] == "점심"), None)
    dinner = next((m for m in meal_stops if m["meal"] == "저녁"), None)
    lunch_at = datetime.strptime("11:30" if lunch and lunch["level"] == "붐빔" else "12:00", "%H:%M")
    plan, prev = [], None

    def add(stop, at):
        nonlocal cur_lat, cur_lng, prev
        d = km(cur_lat, cur_lng, stop["lat"], stop["lng"]) if prev else 0
        mv = travel_min(d) if prev else 0
        arrive = at + timedelta(minutes=mv)
        plan.append({**stop, "icon": KIND_ICON[stop["kind"]], "arrive": arrive.strftime("%H:%M"),
                     "stay_min": STAY[stop["kind"]], "travel_min": mv, "distance_km": round(d, 1)})
        cur_lat, cur_lng, prev = stop["lat"], stop["lng"], stop
        return arrive + timedelta(minutes=STAY[stop["kind"]])

    while todo:
        if lunch and t + timedelta(minutes=30) >= lunch_at and all(p["kind"] != "식사" or p.get("meal") != "점심" for p in plan):
            t = add(lunch, max(t, lunch_at - timedelta(minutes=10)))
            continue
        nxt = min(todo, key=lambda s: km(cur_lat, cur_lng, s["lat"], s["lng"]))
        todo.remove(nxt)
        t = add(nxt, t)
    if lunch and all(p.get("meal") != "점심" for p in plan):
        t = add(lunch, t)
    if dinner:
        t = add(dinner, max(t, datetime.strptime("17:30", "%H:%M")))

    return {
        "regions": [r["label"] for r in res],
        "month": month,
        "date": insight._as_date(when),
        "itinerary": plan,
        "ends_at": t.strftime("%H:%M"),
        "total_travel_min": sum(p["travel_min"] for p in plan),
        "notes": [
            "이동 시간은 직선거리×1.3, 시속 35km 기준 추정 (실제 도로 경로 아님)",
            "장소 혼잡은 월 단위 과거 패턴(와이파이·관광지 유입), 식당은 동네 혼잡 예측 + 추천 모델",
            "점심 시간대가 붐비면 11:30으로 당김" if lunch and lunch["level"] == "붐빔" else "",
        ],
        "sources": db.cite("wifi_monthly", "sight_monthly", "pop_daily", "stores") + ["811 오름 위치", "784 해수욕장 정보"],
    }


def map_data(when: str = "", time_slot: str = "점심", kinds: str = "관광지,오름,해수욕장,명소",
             store_regions: str = "", store_limit: int = 400) -> dict:
    """지도용: 동네 혼잡 원 + 관광 장소 핀 + 좌표 있는 가게 핀."""
    cents = db.rows("SELECT city, emd, lat, lng FROM region_centroids")
    areas = []
    for c in cents:
        f = insight.predict_crowd(f"{c['city']} {c['emd']}", when, time_slot)
        if "forecast" in f and f["forecast"]:
            areas.append({"name": c["emd"], "city": c["city"], "lat": c["lat"], "lng": c["lng"],
                          "level": f["forecast"][0]["level"], "when": f"{f['forecast'][0]['weekday']} {f['forecast'][0]['time_slot']}"})
    levels = _poi_levels(_month(when))
    kind_list = [k.strip() for k in kinds.split(",") if k.strip()]
    pois = [dict(p, level=levels.get(p["poi_id"], "정보 없음"))
            for p in db.rows("SELECT poi_id, kind, name, lat, lng, emd FROM pois") if p["kind"] in kind_list]
    sql = ("SELECT store_id, name, category, emd, lat, lng, naver_listed, open_date FROM stores "
           "WHERE status LIKE '영업%' AND lat IS NOT NULL")
    params: list = []
    if store_regions:
        legal = []
        for n in store_regions.split(","):
            r = regions.resolve(n.strip())
            if r:
                legal += r["legal"]
        if legal:
            sql += f" AND emd IN ({','.join('?' * len(legal))})"
            params += legal
    stores = db.rows(sql + " LIMIT ?", [*params, store_limit])
    return {"areas": areas, "pois": pois, "stores": stores,
            "note": "가게 핀은 네이버 검색으로 좌표를 확인한 가게만 (현재 애월·한림·구좌). 미등록 가게는 목록에서 주소로 확인"}
