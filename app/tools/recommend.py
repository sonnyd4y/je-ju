"""관광객 식당 추천 의사결정 모델: recommend_stores (다기준 가중 점수, MCDA).

후보 가게마다 네 기준을 0~1 점수로 만들고 가중합으로 순위를 매긴다. 같은 입력이면 항상 같은 순위.
  덜 붐빔      그 시간 동네 식당 혼잡 예측 (한산 1.0 / 보통 0.5 / 붐빔 0.0)          ← 583·490·502 (+수요 예측 모델)
  생활권 여유  도민 생활권 과밀도 (여유 1.0 / 주의 0.8 / 과밀 0.5)                    ← 583
  숨은 가게    네이버 지도 미등록 후보 1.0 / 미확인 0.6 / 등록 0.3                       ← 780 + 네이버 검색
  오래된 가게  영업 기간 (10년 이상 1.0, 그 아래는 비례)                                  ← 780 인허가일
가중치 기본 0.35 / 0.25 / 0.20 / 0.20, priority로 강조할 기준을 고르면 그 기준에 0.15를 더 준다.
"""
from datetime import date

from app.data import db, regions
from app.tools import insight
from app.tools.stores import CATEGORY_ALIASES, NON_RESTAURANT

CRITERIA = {"quiet": "덜 붐빔", "balance": "생활권 여유", "hidden": "숨은 가게", "longevity": "오래된 가게"}
BASE_WEIGHTS = {"quiet": 0.35, "balance": 0.25, "hidden": 0.20, "longevity": 0.20}
LEVEL_SCORE = {"한산": 1.0, "보통": 0.5, "붐빔": 0.0}
BALANCE_SCORE = {"여유": 1.0, "주의": 0.8, "과밀": 0.5}
HIDDEN_SCORE = {0: 1.0, None: 0.6, 1: 0.3}


def _weights(priority: str) -> dict:
    w = dict(BASE_WEIGHTS)
    key = next((k for k, v in CRITERIA.items() if priority and (priority == k or priority in v or v in priority)), None)
    if key:
        w[key] += 0.15
        total = sum(w.values())
        w = {k: v / total for k, v in w.items()}
    return {k: round(v, 3) for k, v in w.items()}


def recommend_stores(regions_text: str, category: str = "", when: str = "", time_slot: str = "",
                     priority: str = "", limit: int = 5) -> dict:
    """여러 동네(쉼표로 구분)의 가게를 네 기준 가중 점수로 순위 매겨 추천한다."""
    names = [x.strip() for x in regions_text.replace("/", ",").split(",") if x.strip()]
    if not names:
        return {"error": "지역을 하나 이상 주세요 (예: '애월, 한림, 한경')"}
    w = _weights(priority)
    asof = db.rows("SELECT max(open_date) d FROM stores")[0]["d"] or date.today().isoformat()
    region_info, cands = [], []
    for nm in names[:6]:
        r = regions.resolve(nm)
        if not r:
            region_info.append({"region": nm, "error": "지역을 찾지 못함"})
            continue
        crowd = insight.predict_crowd(nm, when, time_slot or "점심")
        bal = insight.resident_balance(nm)
        lv = crowd["forecast"][0]["level"] if "forecast" in crowd and crowd["forecast"] else "보통"
        region_info.append({"region": r["label"], "crowd_level": lv, "balance": bal.get("level"),
                            "when": crowd["forecast"][0]["weekday"] + " " + crowd["forecast"][0]["time_slot"]
                            if crowd.get("forecast") else ""})
        sql = (f"SELECT store_id, name, category, open_date, addr_road, addr_jibun, emd, naver_listed, lat, lng FROM stores "
               f"WHERE status LIKE '영업%' AND city=? AND emd IN ({','.join('?' * len(r['legal']))})")
        params = [r["city"], *r["legal"]]
        if category:
            cats = CATEGORY_ALIASES.get(category.strip(), [category.strip()])
            sql += f" AND category IN ({','.join('?' * len(cats))})"
            params += cats
        else:
            sql += f" AND coalesce(category,'') NOT IN ({','.join('?' * len(NON_RESTAURANT))}, '기타 휴게음식점', '일반조리판매')"
            params += NON_RESTAURANT
        for s in db.rows(sql, params):
            years = max(0.0, (date.fromisoformat(asof) - date.fromisoformat(s["open_date"])).days / 365.25) if s["open_date"] else 0
            sc = {
                "quiet": LEVEL_SCORE.get(lv, 0.5),
                "balance": BALANCE_SCORE.get(bal.get("level"), 0.8),
                "hidden": HIDDEN_SCORE.get(s["naver_listed"], 0.6),
                "longevity": min(years / 10, 1.0),
            }
            total = sum(w[k] * v for k, v in sc.items())
            cands.append({
                "store_id": s["store_id"], "name": s["name"], "category": s["category"], "region": r["label"],
                "address": (s["addr_road"] or s["addr_jibun"] or "").replace("제주특별자치도 ", "").split(",")[0],
                "years_open": round(years, 1),
                "naver": {1: "등록", 0: "미등록 후보"}.get(s["naver_listed"], "미확인"),
                "score": round(total, 3),
                "score_parts": {CRITERIA[k]: round(w[k] * v, 3) for k, v in sc.items()},
            })
    if not cands:
        return {"error": "조건에 맞는 가게가 없음", "regions": region_info}
    cands.sort(key=lambda c: (-c["score"], -c["years_open"], c["store_id"]))
    top = cands[: max(1, min(limit, 10))]
    return {
        "regions": region_info,
        "candidates": len(cands),
        "weights": {CRITERIA[k]: v for k, v in w.items()},
        "recommendations": top,
        "how_to_read": "score = 네 기준 점수 × 가중치의 합 (0~1). score_parts는 기준별 기여. 동네가 한산하고 생활권 여유가 있을수록, "
                       "네이버에 없는 오래된 동네 가게일수록 높다. 미등록 후보는 영업시간 정보가 없으니 방문 전 확인을 안내할 것.",
        "method": "다기준 가중 점수(MCDA). 같은 입력이면 같은 순위 (재현 가능).",
        "sources": db.cite("stores", "pop_daily", "meal_time_pattern") + ["네이버 지역 검색 (등록 여부)"],
    }
