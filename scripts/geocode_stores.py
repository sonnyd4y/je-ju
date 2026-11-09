"""영업 중인 가게 주소 → 좌표 (네이버 Geocoding). 네이버 미등록 가게도 지도에 표시하기 위해.

이미 좌표가 있는 가게(네이버 검색으로 확인)는 건너뛴다. 결과는 stores.lat/lng 와 geocode_cache 에 저장.
사용법: python scripts/geocode_stores.py 애월 한림 구좌     (지역을 비우면 전체, 약 2만 건)
"""
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.data import db, regions  # noqa: E402
from app.tools import route  # noqa: E402


def main():
    if not route.available():
        sys.exit("네이버 Maps Geocoding을 쓸 수 없음: 네이버 클라우드 콘솔에서 애플리케이션에 Geocoding을 추가(구독)해 주세요.")
    sql, params = "SELECT store_id, addr_road, addr_jibun FROM stores WHERE status LIKE '영업%' AND lat IS NULL", []
    legal = []
    for name in sys.argv[1:]:
        r = regions.resolve(name)
        if r:
            legal += r["legal"]
    if legal:
        sql += f" AND emd IN ({','.join('?' * len(legal))})"
        params = legal
    rows = db.rows(sql, params)
    print(f"좌표 찾을 가게 {len(rows)}곳")

    def one(r):
        for a in (r["addr_road"], r["addr_jibun"]):
            if a:
                g = route.geocode(a.split(",")[0])
                if g:
                    return r["store_id"], g
        return r["store_id"], None

    with ThreadPoolExecutor(4) as pool:
        res = list(pool.map(one, rows))
    ok = [(g[0], g[1], sid) for sid, g in res if g]
    with sqlite3.connect(db.DB_PATH) as con:
        con.executemany("UPDATE stores SET lat=?, lng=? WHERE store_id=?", ok)
    print(f"좌표 저장 {len(ok)}곳, 실패 {len(res) - len(ok)}곳")


if __name__ == "__main__":
    main()
