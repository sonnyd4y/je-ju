"""음식점 인허가 목록(허브 780)을 SQLite stores 테이블로 만든다.

- data/raw/780/ 에 원본 CSV가 있으면 그걸 쓰고, 없으면 data/sample/ 미리보기로 만든다.
- 결과: data/processed/jeju.db  (stores 테이블)

사용법: python scripts/build_store_db.py
"""
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.data.regions import admin_of  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

COLS = {
    "사업장명": "name",
    "업종구분대분류": "biz_type",
    "업종구분소분류": "category",
    "인허가일자": "open_date",
    "인허가취소일자": "license_cancel_date",
    "영업상태명": "status",
    "상세영업상태명": "status_detail",
    "폐업일자": "close_date",
    "휴업시작일자": "pause_start",
    "휴업종료일자": "pause_end",
    "재개업일자": "reopen_date",
    "소재지면적": "area_m2",
    "소재지전체주소": "addr_jibun",
    "도로명전체주소": "addr_road",
    "도로명우편번호": "zipcode",
    "데이터갱신일자": "source_updated_at",
}
DATE_COLS = ["open_date", "license_cancel_date", "close_date", "pause_start", "pause_end", "reopen_date"]


def find_source():
    raw = [p for p in (ROOT / "data/raw/780").glob("*.csv") if "영업및폐업음식점수" not in p.name]
    if raw:
        return raw[0], "full"
    return ROOT / "data/sample/780_음식점목록_미리보기.csv", "sample"


def read_csv(path):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 알 수 없음: {path}")


def to_date(s):
    s = s.fillna("").str.replace(r"\D", "", regex=True).str[:8]
    return pd.to_datetime(s, format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")


def emd_of(addr):
    """주소에서 시(제주시/서귀포시)와 읍면동 추출."""
    if not isinstance(addr, str):
        return None, None
    m = re.search(r"(제주시|서귀포시)\s+(\S+?(?:읍|면|동))(?:\s|$)", addr)
    if m:
        return m.group(1), m.group(2)
    # 도로명주소는 끝 괄호 안에 동 이름이 있다: "... 구남로2길 46, 1층 (아라일동)"
    c = re.search(r"(제주시|서귀포시)", addr)
    d = re.search(r"\(([^()]*?(?:동|리))(?:,[^()]*)?\)\s*$", addr)
    if c and d and d.group(1).endswith("동"):
        return c.group(1), d.group(1)
    return (c.group(1) if c else None), None


def main():
    src, mode = find_source()
    df = read_csv(src).rename(columns=COLS)
    df = df[[c for c in COLS.values() if c in df.columns]]
    for c in DATE_COLS:
        if c in df:
            df[c] = to_date(df[c])
    df["area_m2"] = pd.to_numeric(df["area_m2"], errors="coerce")
    df["name"] = df["name"].str.strip()
    jibun = df["addr_jibun"].map(emd_of)
    road = df["addr_road"].map(emd_of)
    df["city"] = [j[0] or r[0] for j, r in zip(jibun, road)]
    df["emd"] = [j[1] or r[1] for j, r in zip(jibun, road)]
    # 유동인구(583)와 연결하기 위한 행정동. 여러 행정동에 걸치면 쉼표로 묶는다 (예: 서귀동)
    df["admin_emd"] = [",".join(admin_of(c, e)) or None for c, e in zip(df["city"], df["emd"])]
    df["is_open"] = df["status"].fillna("").str.startswith("영업").astype(int)
    df["geocode_addr"] = df["addr_road"].fillna(df["addr_jibun"])
    # 빈 열도 숫자형으로 만들어야 SQLite에 INTEGER/REAL로 저장된다 (None만 있으면 TEXT가 됨)
    df["lat"] = pd.Series(dtype="float64")
    df["lng"] = pd.Series(dtype="float64")
    df["naver_listed"] = pd.Series(dtype="Int64")  # 1=등록, 0=미등록, NULL=미확인
    df.insert(0, "store_id", range(1, len(df) + 1))

    out = ROOT / "data/processed/jeju.db"
    with sqlite3.connect(out) as con:
        df.to_sql("stores", con, if_exists="replace", index=False)
        con.execute("CREATE INDEX IF NOT EXISTS ix_stores_emd ON stores(emd)")
        con.execute("CREATE INDEX IF NOT EXISTS ix_stores_open ON stores(open_date)")
        # 이전에 확인한 네이버 등록 여부·좌표는 다시 반영 (scripts/check_naver.py 결과)
        has = con.execute("SELECT 1 FROM sqlite_master WHERE name='naver_check'").fetchone()
        if has:
            con.execute(
                "UPDATE stores SET naver_listed = (SELECT CASE status WHEN 1 THEN 1 WHEN 0 THEN 0 END FROM naver_check n WHERE n.store_id = stores.store_id), "
                "lat = (SELECT lat FROM naver_check n WHERE n.store_id = stores.store_id), "
                "lng = (SELECT lng FROM naver_check n WHERE n.store_id = stores.store_id) "
                "WHERE store_id IN (SELECT store_id FROM naver_check)"
            )

    print(f"원본: {src.name} ({'전체' if mode == 'full' else '미리보기 샘플'})")
    print(f"저장: {out}  stores {len(df)}건, 영업중 {df['is_open'].sum()}건")
    print(df[["name", "category", "open_date", "status", "city", "emd"]].head(5).to_string(index=False))
    if mode == "sample":
        print("\n※ 샘플로 만들었습니다. 허브에서 780 전체 CSV를 data/raw/780/ 에 넣고 다시 실행하세요.")


if __name__ == "__main__":
    main()
