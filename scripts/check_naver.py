"""지역의 영업 중 가게를 네이버 지역 검색으로 확인해 등록 / 확인 필요 / 미등록 후보로 나눈다.

네이버 검색 API 하루 한도 25,000회. 가게당 1~3회 호출. 이미 확인한 가게는 건너뛴다(--recheck 로 다시).

사용법:
  python scripts/check_naver.py 애월            # 애월읍 전체
  python scripts/check_naver.py 애월 --limit 100
  python scripts/check_naver.py 구좌 --recheck
"""
import argparse
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.data import db, regions  # noqa: E402
from app.tools import naver  # noqa: E402
from app.tools.stores import NON_RESTAURANT  # noqa: E402

WORKERS = 4  # 동시 호출 수 (네이버 하루 한도 25,000회)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("region")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--recheck", action="store_true")
    ap.add_argument("--only-unlisted", action="store_true", help="미등록 후보·확인 필요로 나온 가게만 다시 확인")
    a = ap.parse_args()

    r = regions.resolve(a.region)
    if not r:
        sys.exit(f"지역을 찾지 못함: {a.region}")
    with db.connect() as con:
        con.execute(naver.DDL)
    ph = ",".join("?" * len(r["legal"]))
    skip = ("AND store_id NOT IN (SELECT store_id FROM naver_check WHERE queries LIKE '사장님%')" if a.recheck
            else "AND store_id NOT IN (SELECT store_id FROM naver_check)")
    if a.only_unlisted:
        skip = "AND store_id IN (SELECT store_id FROM naver_check WHERE status IN (0, 2) AND coalesce(queries,'') NOT LIKE '사장님%')"
    stores = db.rows(
        f"SELECT store_id, name, emd, addr_road, addr_jibun, category FROM stores WHERE status LIKE '영업%' "
        f"AND city=? AND emd IN ({ph}) AND coalesce(category,'') NOT IN ({','.join('?' * len(NON_RESTAURANT))}) {skip} "
        "ORDER BY open_date DESC",
        [r["city"], *r["legal"], *NON_RESTAURANT],
    )
    if a.limit:
        stores = stores[: a.limit]
    print(f"{r['label']}: 확인할 가게 {len(stores)}곳")
    count = Counter()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(naver.check_store, s) for s in stores]
        for i, f in enumerate(as_completed(futures), 1):
            try:
                count[naver.STATUS[f.result()["status"]]] += 1
            except naver.NaverError as e:
                print(f"중단 ({i - 1}곳 완료): {e}")
                for rest in futures:
                    rest.cancel()
                break
            if i % 100 == 0:
                print(f"  {i}/{len(stores)}  {dict(count)}", flush=True)

    total = db.rows(
        f"SELECT n.status, count(*) c FROM naver_check n JOIN stores s USING(store_id) "
        f"WHERE s.city=? AND s.emd IN ({ph}) GROUP BY 1",
        [r["city"], *r["legal"]],
    )
    print(f"이번 실행: {dict(count)}")
    print(f"{r['label']} 누적: " + ", ".join(f"{naver.STATUS[t['status']]} {t['c']}" for t in total))


if __name__ == "__main__":
    main()
