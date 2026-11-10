"""관광객 식당 추천 의사결정 모델: recommend_stores (다기준 가중 점수, MCDA).

후보 가게마다 네 기준을 0~1 점수로 만들고 가중합으로 순위를 매긴다. 같은 입력이면 항상 같은 순위.
  덜 붐빔      그 시간 동네 식당 혼잡 예측 (한산 1.0 / 보통 0.5 / 붐빔 0.0)          ← 583·490·502 (+수요 예측 모델)
  생활권 여유  도민 생활권 과밀도 (여유 1.0 / 주의 0.8 / 과밀 0.5)                    ← 583
  숨은 가게    네이버 지도 미등록 후보 1.0 / 미확인 0.6 / 등록 0.3                       ← 780 + 네이버 검색
  오래된 가게  영업 기간 (10년 이상 1.0, 그 아래는 비례)                                  ← 780 인허가일
가중치 기본 0.35 / 0.25 / 0.20 / 0.20, priority로 강조할 기준을 고르면 그 기준에 0.15를 더 준다.

영업 신뢰도 (인허가는 폐업 신고를 안 하면 '영업'으로 남으므로)
  확인됨       네이버에 같은 상호 또는 같은 주소로 등록
  가능성 높음  네이버에 없고 최근 10년 안에 인허가
  확인 필요    네이버에 없고 15년 넘음 → '오래된 가게' 점수 0, 화면에 '방문 전 영업 확인' 표시
  사용자 신고  '문 닫았어요' 신고가 있으면 추천에서 제외 (store_reports)
"""
from datetime import date

from app.data import db, regions
from app.tools import insight
from app.tools.stores import CATEGORY_ALIASES, NON_RESTAURANT, SEASONAL_SQL

CRITERIA = {"quiet": "덜 붐빔", "balance": "생활권 여유", "hidden": "숨은 가게", "longevity": "오래된 가게"}
BASE_WEIGHTS = {"quiet": 0.35, "balance": 0.25, "hidden": 0.20, "longevity": 0.20}
LEVEL_SCORE = {"한산": 1.0, "보통": 0.5, "붐빔": 0.0}
BALANCE_SCORE = {"여유": 1.0, "주의": 0.8, "과밀": 0.5}
HIDDEN_SCORE = {0: 1.0, None: 0.6, 1: 0.3}


def _reported_closed() -> set[int]:
    try:
        return {r["store_id"] for r in db.rows("SELECT store_id FROM store_reports WHERE kind='closed'")}
    except Exception:
        return set()


def _weights(priority: str) -> dict:
    w = dict(BASE_WEIGHTS)
    key = next((k for k, v in CRITERIA.items() if priority and (priority == k or priority in v or v in priority)), None)
    if key:
        w[key] += 0.15
        total = sum(w.values())
        w = {k: v / total for k, v in w.items()}
    return {k: round(v, 3) for k, v in w.items()}


def recommend_stores(regions_text: str, category: str = "", when: str = "", time_slot: str = "",
                     priority: str = "", limit: int = 5, require_coords: bool = False) -> dict:
    """여러 동네(쉼표로 구분)의 가게를 네 기준 가중 점수로 순위 매겨 추천한다."""
    names = [x.strip() for x in regions_text.replace("/", ",").split(",") if x.strip()]
    if not names:
        return {"error": "지역을 하나 이상 주세요 (예: '애월, 한림, 한경')"}
    w = _weights(priority)
    asof = db.rows("SELECT max(open_date) d FROM stores")[0]["d"] or date.today().isoformat()
    region_info, cands = [], []
    reported = _reported_closed()
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
        sql = (f"SELECT s.store_id, s.name, s.category, s.open_date, s.addr_road, s.addr_jibun, s.emd, s.naver_listed, s.lat, s.lng, "
               f"n.status AS n_status, n.naver_title, n.addr_match FROM stores s LEFT JOIN naver_check n USING(store_id) "
               f"WHERE s.status LIKE '영업%' AND NOT {SEASONAL_SQL.replace('name', 's.name')} AND s.city=? AND s.emd IN ({','.join('?' * len(r['legal']))})")
        params = [r["city"], *r["legal"]]
        if require_coords:  # 지도·일정용: 좌표 있는 가게만
            sql += " AND s.lat IS NOT NULL"
        if category:
            cats = CATEGORY_ALIASES.get(category.strip(), [category.strip()])
            sql += f" AND s.category IN ({','.join('?' * len(cats))})"
            params += cats
        else:
            sql += f" AND coalesce(s.category,'') NOT IN ({','.join('?' * len(NON_RESTAURANT))}, '기타 휴게음식점', '일반조리판매')"
            params += NON_RESTAURANT
        for s in db.rows(sql, params):
            years = max(0.0, (date.fromisoformat(asof) - date.fromisoformat(s["open_date"])).days / 365.25) if s["open_date"] else 0
            # 네이버 상태: 등록 / 다른 상호로 등록(같은 주소) / 미등록 후보 / 확인 필요 / 미확인
            if s["n_status"] == 1:
                nv = "등록"
            elif s["n_status"] == 2 and s["addr_match"]:
                nv = "다른 상호로 등록"
            elif s["n_status"] == 2:
                nv = "확인 필요"
            elif s["n_status"] == 0:
                nv = "미등록 후보"
            else:
                nv = "미확인"
            verified = nv in ("등록", "다른 상호로 등록")
            confidence = "확인됨" if verified else "가능성 높음" if years < 10 else "확인 필요" if years >= 15 else "보통"
            if s["store_id"] in reported:
                continue
            sc = {
                "quiet": LEVEL_SCORE.get(lv, 0.5),
                "balance": BALANCE_SCORE.get(bal.get("level"), 0.8),
                "hidden": {"미등록 후보": 1.0, "미확인": 0.6, "확인 필요": 0.5}.get(nv, 0.3),
                # 오래 영업했다는 가산점은 지금도 영업이 확인된 가게에만 (폐업 신고만 안 한 가게를 높이지 않게)
                "longevity": min(years / 10, 1.0) if verified else 0.0,
            }
            total = sum(w[k] * v for k, v in sc.items())
            cands.append({
                "store_id": s["store_id"], "name": s["name"], "category": s["category"], "region": r["label"],
                "address": (s["addr_road"] or s["addr_jibun"] or "").replace("제주특별자치도 ", "").split(",")[0],
                "years_open": round(years, 1),
                "open_confidence": confidence,
                "naver": nv,
                "naver_name": s["naver_title"] if nv in ("등록", "다른 상호로 등록") and s["naver_title"] != s["name"] else None,
                "lat": s["lat"], "lng": s["lng"],
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
        "how_to_read": "years_open은 인허가일부터 지난 햇수예요. 주인·상호·메뉴가 바뀌어도 처음 인허가일이 이어질 수 있으니 "
                       "'개업 N년'·'N년 된 가게'라고 단정하지 말고 '인허가 기준 N년'이라고 말하세요. "
                       "score = 네 기준 점수 × 가중치의 합 (0~1). score_parts는 기준별 기여. 동네가 한산하고 생활권 여유가 있을수록, "
                       "네이버에 없는 오래된 동네 가게일수록 높다. 미등록 후보는 영업시간 정보가 없으니 방문 전 확인을 안내할 것.",
        "method": "다기준 가중 점수(MCDA). 같은 입력이면 같은 순위 (재현 가능).",
        "sources": db.cite("stores", "pop_daily", "meal_time_pattern") + ["네이버 지역 검색 (등록 여부)"],
    }
