"""SQLite(data/processed/jeju.db) 조회 도우미.

센터 PC에서 반출 불가 데이터를 쓸 때는 JEJU_DB 환경변수로 다른 DB 파일을 지정해 교체한다.
"""
import os
import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("JEJU_DB", ROOT / "data/processed/jeju.db"))


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"{DB_PATH} 가 없습니다. scripts/build_store_db.py, scripts/build_insight_db.py 를 먼저 실행하세요."
        )
    con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)  # 동시 쓰기 시 잠금 대기
    con.row_factory = sqlite3.Row
    return con


def query(sql: str, params=()) -> pd.DataFrame:
    with closing(connect()) as con:
        return pd.read_sql(sql, con, params=params)


def rows(sql: str, params=()) -> list[dict]:
    with closing(connect()) as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


@lru_cache(maxsize=1)
def sources() -> dict[str, dict]:
    """테이블별 원본 데이터 ID·기간 (응답 근거 표시용)."""
    out = {}
    try:
        out = {r["table"]: r for r in rows("SELECT * FROM data_sources")}
    except Exception:
        pass
    try:
        last = rows("SELECT max(open_date) d FROM stores")[0]["d"]
        out["stores"] = {"source": "780", "period": f"인허가 ~{last}"}
    except Exception:
        pass
    return out


DATA_NAMES = {
    "780": "제주특별자치도 음식점 목록",
    "583": "읍면동 단위 내국인 유동인구",
    "490": "시간대별 외식업 이용자수",
    "502": "시간대별 카드 이용금액 현황",
    "504": "요일별 카드 이용건수",
    "495": "메뉴별 외식업 매출액",
    "1048": "업종별 성별 카드 이용 정보",
    "568": "와이파이 장소별 사용자 현황",
    "591": "관광지별 내국인 유입자 수",
    "592": "관광지별 외국인 유입자 수",
    "903": "구글 음식점 리뷰 원천데이터",
    "906": "구글 음식점 리뷰 분석 데이터",
}


def cite(*tables: str) -> list[str]:
    """['읍면동 단위 내국인 유동인구(583, 2025-08-01~2025-11-30)', ...]"""
    out = []
    src = sources()
    for t in tables:
        s = src.get(t)
        if not s:
            continue
        for i in str(s["source"]).split(","):
            label = f"{DATA_NAMES.get(i, i)}({i}, {s['period']})"
            if label not in out:
                out.append(label)
    return out
