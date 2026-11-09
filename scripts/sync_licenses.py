"""인허가 갱신 (sync_licenses): 새로 받은 음식점 인허가 파일을 지금 DB와 비교해 바뀐 점만 반영한다.

공공 인허가 데이터는 파일로 제공되므로, 새 파일을 받을 때마다 비교(diff)하는 방식.
  - 신규 개업: 새 파일에만 있는 가게 → 새 store_id로 추가
  - 폐업·영업 상태 변경: 같은 가게(상호+주소+인허가일)의 상태가 바뀜 → 상태·폐업일 갱신
  - 기존 가게의 store_id, 네이버 등록 여부, 좌표는 그대로 유지
  - 바뀐 내역은 license_changes 테이블에 날짜와 함께 기록 (Agent가 '최근 개업·폐업'에 사용)

사용법:
  python scripts/sync_licenses.py 새파일.csv
  python scripts/sync_licenses.py 새파일.csv --dry-run     (반영하지 않고 바뀐 점만 보기)
"""
import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from scripts.build_store_db import prepare, store_key  # noqa: E402
from app.data import db  # noqa: E402

DDL = ("CREATE TABLE IF NOT EXISTS license_changes (synced_on TEXT, store_id INTEGER, change TEXT, "
       "name TEXT, city TEXT, emd TEXT, category TEXT, before TEXT, after TEXT)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    new = prepare(Path(a.csv))
    new["key"] = store_key(new)
    new = new.drop_duplicates("key")
    with sqlite3.connect(db.DB_PATH) as con:
        old = pd.read_sql("SELECT * FROM stores", con)
    old["key"] = store_key(old)
    old_by_key = old.drop_duplicates("key").set_index("key")

    added = new[~new.key.isin(old_by_key.index)]
    both = new[new.key.isin(old_by_key.index)]
    changed = both[both.status.values != old_by_key.loc[both.key, "status"].values]
    gone = old_by_key[~old_by_key.index.isin(new.key) & old_by_key.status.str.startswith("영업", na=False)]

    today = date.today().isoformat()
    print(f"신규 {len(added)}곳 · 상태 변경 {len(changed)}곳 (그중 폐업 {changed.status.str.startswith('폐업', na=False).sum()}곳) · "
          f"새 파일에 없는 영업 가게 {len(gone)}곳")
    if len(added):
        print("신규 예:", ", ".join(f"{r.name}({r.emd})" for r in added.head(5).itertuples()))
    if a.dry_run:
        return

    logs = []
    with sqlite3.connect(db.DB_PATH) as con:
        con.execute(DDL)
        next_id = con.execute("SELECT max(store_id) FROM stores").fetchone()[0] + 1
        cols = [c for c in old.columns if c not in ("key",)]
        rows = added.assign(store_id=range(next_id, next_id + len(added)))
        rows[[c for c in cols if c in rows.columns]].to_sql("stores", con, if_exists="append", index=False)
        logs += [(today, r.store_id, "신규", r.name, r.city, r.emd, r.category, None, r.status) for r in rows.itertuples()]
        for r in changed.itertuples():
            o = old_by_key.loc[r.key]
            con.execute("UPDATE stores SET status=?, status_detail=?, close_date=?, is_open=? WHERE store_id=?",
                        [r.status, r.status_detail, r.close_date, int(str(r.status).startswith("영업")), int(o.store_id)])
            kind = "폐업" if str(r.status).startswith("폐업") else "상태 변경"
            logs.append((today, int(o.store_id), kind, r.name, r.city, r.emd, r.category, o.status, r.status))
        for k, o in gone.iterrows():
            logs.append((today, int(o.store_id), "목록에서 사라짐", o["name"], o.city, o.emd, o.category, o.status, None))
        con.executemany("INSERT INTO license_changes VALUES (?,?,?,?,?,?,?,?,?)", logs)
    print(f"반영 완료: 변경 기록 {len(logs)}건 (license_changes)")


if __name__ == "__main__":
    main()
