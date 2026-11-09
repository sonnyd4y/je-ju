"""관광 장소(POI) 테이블: 오름·해수욕장·관광지·명소 + 장소별 월별 혼잡도.

출처
  811 오름 위치 (좌표 포함)
  784 해수욕장 정보 (이름 → 네이버 지역 검색으로 좌표)
  591·592 관광지별 내·외국인 유입자 (이름 → 좌표, 월별 방문자)
  568 와이파이 장소별 사용자 (상위 명소 → 좌표, 월별 이용자)

결과 (jeju.db)
  pois        poi_id, kind(오름/해수욕장/관광지/명소), name, lat, lng, address, city, emd(행정동), source
  poi_month   poi_id, month(1~12), visitors(월평균), factor(이 장소 평균 대비), level(한산/보통/붐빔), source
              level: 장소 규모 순위(0~1) × 월 계수의 제주 전체 분포 → 하위 40% 한산, 상위 20% 붐빔
사용법: python scripts/build_pois.py   (네이버 검색 약 150회)
"""
import math
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.data import db  # noqa: E402
from app.tools import naver  # noqa: E402

TOURIST_CATS = ("여행", "관광", "명소", "해수욕장", "해변", "시장", "공원", "폭포", "오름", "박물관", "미술관", "휴양림", "거리", "테마")
SKIP_WIFI = ("의료원", "도서관", "보건", "버스", "터미널", "공항", "청사", "센터", "학교", "경기장", "코스", "야영장", "주민", "읍", "면사무소")


def read_csv(path):
    for enc in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc)
        except UnicodeDecodeError:
            continue


def geocode(query: str, must: str = "") -> dict | None:
    """네이버 지역 검색 첫 결과 중 제주 주소이고 이름이 비슷한 것."""
    for it in naver.search(query, display=5):
        addr = f"{it.get('roadAddress', '')} {it.get('address', '')}"
        if "제주" not in addr:
            continue
        if must and fuzz.partial_ratio(re.sub(r"\s", "", must), re.sub(r"\s", "", it["title"])) < 70:
            continue
        return {"lat": naver._coord(it["mapy"]), "lng": naver._coord(it["mapx"]),
                "address": it.get("roadAddress") or it.get("address"), "category": it.get("category", ""), "title": it["title"]}
    return None


def nearest_region(lat, lng, cents):
    best = min(cents, key=lambda c: (c["lat"] - lat) ** 2 + ((c["lng"] - lng) * math.cos(math.radians(lat))) ** 2)
    return best["city"], best["emd"]


def main():
    cents = db.rows("SELECT city, emd, lat, lng FROM region_centroids")
    pois = []

    # 오름 (좌표 있음)
    o = read_csv(ROOT / "data/raw/811/811_api.csv")
    for r in o.itertuples():
        pois.append({"kind": "오름", "name": r.placeName, "lat": float(r.latitude), "lng": float(r.longitude),
                     "address": r.addressDoro if isinstance(r.addressDoro, str) else r.addressJibun, "source": "811"})

    # 해수욕장
    b = read_csv(ROOT / "data/raw/784/제주특별자치도해수욕장정보.csv")
    for name in sorted(b["해변명"].dropna().unique()):
        g = geocode(f"제주 {name}해수욕장", must=name)
        if g:
            pois.append({"kind": "해수욕장", "name": f"{name}해수욕장", **{k: g[k] for k in ("lat", "lng", "address")}, "source": "784"})

    # 관광지 (591·592)
    sights = db.rows("SELECT DISTINCT sight FROM sight_monthly")
    for s in sights:
        g = geocode(f"제주 {s['sight']}", must=s["sight"])
        if g:
            pois.append({"kind": "관광지", "name": s["sight"], **{k: g[k] for k in ("lat", "lng", "address")}, "source": "591,592"})

    # 와이파이 상위 명소 (최근 1년 이용자 상위, 관광 성격만)
    w = db.query("SELECT place, sum(users) u FROM wifi_monthly WHERE place_type='장소' AND ym >= '202410' "
                 "GROUP BY place ORDER BY u DESC LIMIT 120")
    have = [p["name"] for p in pois]
    for place in w.place:
        if any(k in place for k in SKIP_WIFI) or any(fuzz.ratio(place, h) > 80 for h in have):
            continue
        g = geocode(f"제주 {place}", must=place)
        if g and any(k in g["category"] for k in TOURIST_CATS):
            pois.append({"kind": "명소", "name": place, **{k: g[k] for k in ("lat", "lng", "address")}, "source": "568"})

    df = pd.DataFrame(pois).drop_duplicates(subset=["name"])
    df = df[(df.lat.between(33.0, 34.0)) & (df.lng.between(126.0, 127.1))]  # 제주 범위 밖 제거
    df.insert(0, "poi_id", range(1, len(df) + 1))
    regs = [nearest_region(a, b_, cents) for a, b_ in zip(df.lat, df.lng)]
    df["city"] = [r[0] for r in regs]
    df["emd"] = [r[1] for r in regs]

    # 장소별 월별 방문 (와이파이 이름 매칭 우선, 없으면 관광지 유입)
    wifi = db.query("SELECT ym, place, users FROM wifi_monthly WHERE place_type='장소'")
    wifi_names = wifi.place.unique().tolist()
    sight = db.query('SELECT ym, sight, coalesce(domestic,0) + coalesce("foreign",0) users FROM sight_monthly')
    rows = []
    for p in df.itertuples():
        key = re.sub(r"(해수욕장|\s)", "", p.name)
        # 이름이 와이파이 장소명 안에 들어 있으면 우선 ('협재' → '협재 해변(협재해수욕장)')
        contains = [n for n in wifi_names if len(key) >= 2 and key in re.sub(r"\s", "", n)]
        cand = max(contains or wifi_names, key=lambda n: fuzz.token_set_ratio(key, re.sub(r"\s", "", n)))
        series, src = None, None
        if contains or fuzz.token_set_ratio(key, re.sub(r"\s", "", cand)) >= 85:
            series, src = wifi[wifi.place == cand], f"568:{cand}"
        elif p.name in set(sight.sight):
            series, src = sight[sight.sight == p.name].rename(columns={"sight": "place"}), "591,592"
        if series is None or series.empty:
            continue
        s = series.assign(month=series.ym.str[4:6].astype(int)).groupby("month").users.mean()
        for m, v in s.items():
            rows.append({"poi_id": p.poi_id, "month": m, "visitors": round(v), "factor": round(v / s.mean(), 3), "source": src})
    pm = pd.DataFrame(rows)
    if not pm.empty:
        size = pm.groupby("poi_id").visitors.mean().rank(pct=True)
        pm["score"] = pm.poi_id.map(size) * pm.factor
        lo, hi = pm.score.quantile([0.4, 0.8])
        pm["level"] = pm.score.map(lambda x: "한산" if x < lo else "보통" if x < hi else "붐빔")
        pm = pm.drop(columns="score")

    with sqlite3.connect(db.DB_PATH) as con:
        df[["poi_id", "kind", "name", "lat", "lng", "address", "city", "emd", "source"]].to_sql("pois", con, if_exists="replace", index=False)
        pm.to_sql("poi_month", con, if_exists="replace", index=False)
    print(df.kind.value_counts().to_dict(), f"/ 월별 혼잡 있는 장소 {pm.poi_id.nunique() if not pm.empty else 0}곳")


if __name__ == "__main__":
    main()
