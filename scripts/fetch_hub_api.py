"""제주데이터허브 API형 데이터를 받아 data/raw/<ID>/ 에 CSV로 저장한다.

호출 형식: https://open.jejudatahub.net/api/proxy/{dataKey}/{projectKey}?{params}
- projectKey: .env 의 JEJUDATAHUB_PROJECT_KEY
- 페이지: number(1부터), limit(최대 100. 200 이상은 서버 오류)
- 응답: {"totCnt": 전체건수, "hasMore": bool, "data": [...]}
- 쿼터: 데이터별 하루 1000회. 유동인구(583)는 하루치 688건 = 7회 → 하루에 약 4개월치. 2026-08-31까지 제공 확인(2026-11-04 기준)

월 단위로 나눠 data/raw/<ID>/parts/ 에 저장하므로, 쿼터가 끝나 중단돼도
다음 날 같은 명령을 다시 실행하면 받은 달은 건너뛰고 이어서 받는다.

사용법:
  python scripts/fetch_hub_api.py                          # 전체 (기본 기간)
  python scripts/fetch_hub_api.py 583 --from 2025-04 --to 2025-07
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://open.jejudatahub.net/api/proxy"
LIMIT = 100
sys.stdout.reconfigure(encoding="utf-8")

# id: (이름, dataKey, 날짜형식, 기본 기간)
APIS = {
    583: ("읍면동 내국인 유동인구", "Daaa1t3at3tt8a8DD3t55538t35Dab1t", "%Y%m%d", ("2025-09", "2026-08")),
    591: ("관광지별 내국인 유입자", "bt11Daa5at1tat515DDtaa9D5aa99t11", "%Y%m", ("2018-01", "2024-12")),
    592: ("관광지별 외국인 유입자", "12ta2a2t291tDbbabtbD9t1a219tbDbt", "%Y%m", ("2018-01", "2024-12")),
    811: ("오름 위치", "1Dttb1tab8tD88Dtat11111at1t1atD8", None, None),
    837: ("관광 숙박업", "ttbttaD3aaa3ta8bbtDtaDD18t37aD17", None, None),
}


class QuotaError(Exception):
    pass


def call(data_key, project_key, params):
    url = f"{BASE}/{data_key}/{project_key}?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            if e.code == 429 or "quota" in body.lower() or "쿼터" in body:
                raise QuotaError(body[:200])
            if attempt == 2:
                raise RuntimeError(f"HTTP {e.code}: {body[:200]}")
        time.sleep(2 * (attempt + 1))


def fetch_all_pages(data_key, project_key, params):
    rows, number = [], 1
    while True:
        resp = call(data_key, project_key, {**params, "number": number, "limit": LIMIT})
        rows += resp.get("data") or []
        if not resp.get("hasMore"):
            return rows, resp.get("totCnt")
        number += 1
        time.sleep(0.2)


def fetch(i, project_key, start=None, end=None):
    name, data_key, fmt, default = APIS[i]
    out_dir = ROOT / f"data/raw/{i}"
    parts = out_dir / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    print(f"[{i}] {name}")

    if fmt is None:
        chunks = [("all", {})]
    elif fmt == "%Y%m":  # 월별 데이터는 전체 기간을 한 번에
        s, e = start or default[0], end or default[1]
        chunks = [(f"{s}_{e}", {"startDate": s.replace("-", ""), "endDate": e.replace("-", "")})]
    else:  # 일별 데이터는 월 단위로 분할
        s, e = start or default[0], end or default[1]
        today = pd.Timestamp.today().normalize()
        chunks = []
        for p in pd.period_range(s, e, freq="M"):
            a, b = p.start_time, min(p.end_time.normalize(), today)
            if a > today:
                break
            chunks.append((p.strftime("%Y-%m"), {"startDate": a.strftime(fmt), "endDate": b.strftime(fmt)}))

    for tag, params in chunks:
        part = parts / f"{tag}.csv"
        if part.exists() and tag != "all":
            print(f"  {tag}: 이미 받음, 건너뜀")
            continue
        rows, total = fetch_all_pages(data_key, project_key, params)
        pd.DataFrame(rows).to_csv(part, index=False, encoding="utf-8-sig")
        print(f"  {tag}: {len(rows)}건 (서버 기준 {total}건)")

    files = sorted(parts.glob("*.csv"))
    df = pd.concat([pd.read_csv(f, dtype=str) for f in files if f.stat().st_size > 3], ignore_index=True)
    df.to_csv(out_dir / f"{i}_api.csv", index=False, encoding="utf-8-sig")
    print(f"  → 합본 {len(df)}건: data/raw/{i}/{i}_api.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", type=int)
    ap.add_argument("--from", dest="start")
    ap.add_argument("--to", dest="end")
    a = ap.parse_args()

    load_dotenv(ROOT / ".env")
    key = os.getenv("JEJUDATAHUB_PROJECT_KEY", "").strip()
    if not key:
        sys.exit(".env 에 JEJUDATAHUB_PROJECT_KEY 를 넣어 주세요 (허브 > 내 프로젝트 화면).")

    for i in a.ids or APIS:
        if i not in APIS:
            print(f"[{i}] API형 데이터가 아닙니다. 건너뜀")
            continue
        try:
            fetch(i, key, a.start, a.end)
        except QuotaError as e:
            print(f"[{i}] 오늘 쿼터 소진으로 중단. 내일 같은 명령을 다시 실행하면 이어서 받습니다. ({e})")
        except Exception as e:
            print(f"[{i}] 실패: {e}")


if __name__ == "__main__":
    main()
