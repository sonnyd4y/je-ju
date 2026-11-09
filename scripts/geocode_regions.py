"""읍면동 중심 좌표: 네이버 지역 검색으로 각 행정동의 주민센터·읍면사무소 위치를 찾아 region_centroids 테이블에 저장.

지도에서 동네별 혼잡도 원을 그리는 데 쓴다. 43회 호출 (네이버 하루 한도 25,000회).
사용법: python scripts/geocode_regions.py
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.data import db, regions  # noqa: E402
from app.tools import naver  # noqa: E402

OFFICE = {"읍": ["읍사무소", "읍행정복지센터"], "면": ["면사무소", "면행정복지센터"], "동": ["주민센터", "행정복지센터"]}


def main():
    out, miss = [], []
    for (city, emd) in regions.ADMIN_TO_LEGAL:
        found = None
        for suffix in OFFICE[emd[-1]]:
            for it in naver.search(f"{city} {emd} {suffix}", display=5):
                addr = f"{it.get('roadAddress', '')} {it.get('address', '')}"
                # 이름에 그 동네 이름이 있어야 한다 ('삼도1동' 검색에 '이도2동주민센터'가 나오는 경우 제외)
                if city in addr and emd in it["title"].replace(" ", "") and (
                        "주민센터" in it["title"] or "사무소" in it["title"] or "행정복지센터" in it["title"]):
                    found = it
                    break
            if found:
                break
        if found:
            out.append((city, emd, naver._coord(found["mapy"]), naver._coord(found["mapx"]), found["title"]))
        else:
            miss.append(f"{city} {emd}")
    with sqlite3.connect(db.DB_PATH) as con:
        con.execute("CREATE TABLE IF NOT EXISTS region_centroids (city TEXT, emd TEXT, lat REAL, lng REAL, source TEXT, "
                    "PRIMARY KEY (city, emd))")
        con.executemany("INSERT OR REPLACE INTO region_centroids VALUES (?,?,?,?,?)", out)
    print(f"저장 {len(out)}곳, 못 찾음 {len(miss)}곳: {miss}")
    for r in out[:5]:
        print(r)


if __name__ == "__main__":
    main()
