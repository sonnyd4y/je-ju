"""네이버 클라우드 Maps: 길찾기(Directions 5)·주소→좌표(Geocoding).

키: .env 의 NCP_CLIENT_ID / NCP_CLIENT_SECRET (없으면 NAVER_SEARCH_CLIENT_ID / SECRET 로 시도 — 같은 애플리케이션에
     Maps API를 함께 켠 경우). 호출 결과는 jeju.db 에 캐시해 같은 구간·주소는 다시 부르지 않는다.
Maps 구독이 안 돼 있거나 실패하면 None 을 돌려주고, 호출 쪽은 직선거리 추정으로 대체한다.
"""
import json
import os
import time

import requests
from dotenv import load_dotenv

from app.data import db

load_dotenv(db.ROOT / ".env")

HOSTS = ["https://maps.apigw.ntruss.com", "https://naveropenapi.apigw.ntruss.com"]
_session = requests.Session()
_disabled_until = 0.0  # 구독 없음(401) 같은 오류가 나면 잠시 시도를 멈춘다

DDL = [
    "CREATE TABLE IF NOT EXISTS route_cache (k TEXT PRIMARY KEY, v TEXT, created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS geocode_cache (address TEXT PRIMARY KEY, lat REAL, lng REAL, created_at TEXT)",
]


def _keys():
    for a, b in (("NCP_CLIENT_ID", "NCP_CLIENT_SECRET"), ("NAVER_SEARCH_CLIENT_ID", "NAVER_SEARCH_CLIENT_SECRET")):
        cid, sec = os.getenv(a, "").strip(), os.getenv(b, "").strip()
        if cid and sec:
            return cid, sec
    return None


def _get(path: str, params: dict) -> dict | None:
    global _disabled_until
    keys = _keys()
    if not keys or time.time() < _disabled_until:
        return None
    for host in HOSTS:
        try:
            r = _session.get(host + path, params=params, timeout=15,
                             headers={"x-ncp-apigw-api-key-id": keys[0], "x-ncp-apigw-api-key": keys[1]})
        except requests.exceptions.RequestException:
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code in (401, 403):  # 구독 없음: 10분 동안 다시 시도하지 않음
            _disabled_until = time.time() + 600
            return None
    return None


def _cache(sql: str, params=()):
    with db.connect() as con:
        for d in DDL:
            con.execute(d)
        return con.execute(sql, params).fetchall()


def available() -> bool:
    """Maps API를 쓸 수 있는지 (구독·키 확인용 시험 호출)."""
    return geocode("제주특별자치도 제주시 문연로 6") is not None


def geocode(address: str) -> tuple[float, float] | None:
    """주소 → (위도, 경도)."""
    if not address:
        return None
    hit = _cache("SELECT lat, lng FROM geocode_cache WHERE address=?", [address])
    if hit:
        return (hit[0][0], hit[0][1]) if hit[0][0] is not None else None
    d = _get("/map-geocode/v2/geocode", {"query": address})
    if d is None:
        return None
    a = (d.get("addresses") or [None])[0]
    lat, lng = (float(a["y"]), float(a["x"])) if a else (None, None)
    _cache("INSERT OR REPLACE INTO geocode_cache VALUES (?,?,?,datetime('now'))", [address, lat, lng])
    return (lat, lng) if a else None


def driving(a: tuple[float, float], b: tuple[float, float]) -> dict | None:
    """두 지점 (위도, 경도) 사이 자동차 길찾기: 걸리는 시간(분), 거리(km), 경로 좌표 [[위도, 경도], ...]."""
    k = f"{a[0]:.5f},{a[1]:.5f}>{b[0]:.5f},{b[1]:.5f}"
    hit = _cache("SELECT v FROM route_cache WHERE k=?", [k])
    if hit:
        return json.loads(hit[0][0])
    d = _get("/map-direction/v1/driving", {"start": f"{a[1]},{a[0]}", "goal": f"{b[1]},{b[0]}", "option": "trafast"})
    if not d or d.get("code") != 0:
        return None
    r = d["route"]["trafast"][0]
    path = r.get("path", [])
    step = max(1, len(path) // 200)  # 지도에 그릴 만큼만 줄인다
    out = {
        "minutes": round(r["summary"]["duration"] / 60000),
        "km": round(r["summary"]["distance"] / 1000, 1),
        "path": [[p[1], p[0]] for p in path[::step]] + ([[path[-1][1], path[-1][0]]] if path else []),
        "source": "네이버 Directions 5 (실시간 교통 반영 경로)",
    }
    _cache("INSERT OR REPLACE INTO route_cache VALUES (?,?,datetime('now'))", [k, json.dumps(out)])
    return out
