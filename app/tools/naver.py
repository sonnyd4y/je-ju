"""네이버 지도 등록 여부 판별: check_naver_listed (네이버 API HUB 지역 검색).

판별 방법 (가게 1곳당 검색 최대 2회)
  1. "상호 + 읍면동"으로 검색, 결과가 없으면 "제주 + 상호"로 한 번 더
  2. 검색 결과마다 상호 유사도와 주소 일치(도로명+건물번호, 또는 법정동+지번)를 계산
  3. 상호 유사 + 주소 일치 → 등록
     둘 중 하나만 맞음      → 확인 필요 (상호 변경, 이전, 같은 이름 다른 가게 등)
     둘 다 아님             → 미등록 후보
(이름 끝 숫자·지점명을 뗀 상호로도 검색, 가게당 최대 3회)
결과는 naver_check 테이블에 저장하고 stores.naver_listed / lat / lng 에 반영한다.
"""
import html
import os
import re
import time
from datetime import datetime

import requests
from dotenv import load_dotenv
from rapidfuzz import fuzz

from app.data import db

load_dotenv(db.ROOT / ".env")

URL = "https://naverapihub.apigw.ntruss.com/search/v1/local"
STATUS = {1: "등록", 0: "미등록 후보", 2: "확인 필요"}

DDL = """
CREATE TABLE IF NOT EXISTS naver_check (
    store_id INTEGER PRIMARY KEY,
    status INTEGER,
    naver_title TEXT,
    naver_category TEXT,
    naver_road TEXT,
    naver_jibun TEXT,
    lat REAL,
    lng REAL,
    name_score INTEGER,
    addr_match INTEGER,
    queries TEXT,
    checked_at TEXT
)
"""


class NaverError(Exception):
    pass


# 연결을 재사용해야 호출당 8초 → 0.8초 (매번 새 연결을 맺으면 TLS 연결 설정이 느림)
_session = requests.Session()


def _keys():
    cid, sec = os.getenv("NAVER_SEARCH_CLIENT_ID", "").strip(), os.getenv("NAVER_SEARCH_CLIENT_SECRET", "").strip()
    if not cid or not sec:
        raise NaverError(".env 에 NAVER_SEARCH_CLIENT_ID / NAVER_SEARCH_CLIENT_SECRET 이 없음")
    return cid, sec


def search(query: str, display: int = 5) -> list[dict]:
    cid, sec = _keys()
    for attempt in range(3):
        try:
            r = _session.get(
                URL,
                params={"query": query, "display": display, "format": "json"},
                headers={"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": sec},
                timeout=15,
            )
        except requests.exceptions.RequestException:  # 연결 끊김은 잠시 뒤 다시 시도
            time.sleep(2 + attempt * 3)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(1 + attempt * 2)
            continue
        if r.status_code != 200:
            raise NaverError(f"HTTP {r.status_code}: {r.text[:200]}")
        items = r.json().get("items", [])
        for it in items:
            it["title"] = html.unescape(re.sub(r"<[^>]+>", "", it.get("title", "")))
        return items
    raise NaverError("네이버 검색 응답 없음 (재시도 초과)")


# ---------- 매칭 ----------

def _norm_name(s: str) -> str:
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s or "")
    s = re.sub(r"(주식회사|㈜|제주점|본점|직영점)", "", s)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s).lower()


def name_score(a: str, b: str) -> int:
    a, b = _norm_name(a), _norm_name(b)
    if not a or not b:
        return 0
    s = fuzz.ratio(a, b)
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 2 and short in long_:  # '자매국수' vs '자매국수 본점', '고집돌우럭' vs '고집돌우럭중문점'
        s = max(s, 85)
    return round(s)


def road_key(addr: str | None) -> str | None:
    """'제주특별자치도 제주시 항골남길 46, 1층 (이호일동)' → '항골남길46'"""
    if not addr:
        return None
    m = re.search(r"([가-힣0-9]+(?:로|길))\s*(\d+(?:-\d+)?)", addr)
    return f"{m.group(1)}{m.group(2)}" if m else None


def jibun_key(addr: str | None) -> str | None:
    """'제주특별자치도 제주시 이호일동 651-3' → '이호일동651-3', '애월읍 애월리 123' → '애월리123'"""
    if not addr:
        return None
    m = re.search(r"([가-힣0-9]+(?:동|리|가))\s*(?:산\s*)?(\d+(?:-\d+)?)", addr)
    return f"{m.group(1)}{m.group(2)}" if m else None


def _coord(v: str) -> float | None:
    """네이버 좌표는 1e-7 단위 정수 문자열 ('1264591844' → 126.4591844)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x / 1e7 if abs(x) > 1000 else x


def judge(store: dict, items: list[dict]) -> dict:
    """가게 1곳 vs 검색 결과 → 판별."""
    rk, jk = road_key(store.get("addr_road")), jibun_key(store.get("addr_jibun"))
    best = None
    for it in items:
        ns = name_score(store["name"], it["title"])
        addr = (rk and rk == road_key(it.get("roadAddress"))) or (jk and jk == jibun_key(it.get("address")))
        score = ns + (100 if addr else 0)
        if best is None or score > best["_score"]:
            best = {"_score": score, "item": it, "name_score": ns, "addr_match": bool(addr)}
    if best is None:
        return {"status": 0, "name_score": 0, "addr_match": False, "item": None}
    ok_name = best["name_score"] >= 70
    if ok_name and best["addr_match"]:
        status = 1
    elif ok_name or best["addr_match"]:
        status = 2
    else:
        status = 0
    return {"status": status, **{k: best[k] for k in ("name_score", "addr_match", "item")}}


def base_name(name: str) -> str:
    """'자담치킨애월점1' → '자담치킨', '보배쌤보리김치와게장제주공항점' → '보배쌤보리김치와게장'"""
    s = re.sub(r"\d+$", "", name.strip())                 # 인허가 중복 구분 숫자
    s = re.sub(r"\(.*?\)", "", s)
    m = re.match(r"^(.{2,})([가-힣]{2,5}점)$", s)       # 가장 짧은 '○○점' 지점명만 뗀다
    if m:
        s = re.sub(r"(제주|제주시|서귀포)$", "", m.group(1)) or m.group(1)
    return s.strip() or name


def check_store(store: dict) -> dict:
    """가게 1곳을 네이버에서 찾아 판별하고 저장한다. 등록으로 판별되면 바로 멈춘다 (상호로 최대 3회 + 상호 앞부분 1회)."""
    emd = store.get("emd") or ""
    short = base_name(store["name"])
    candidates = [f"{store['name']} {emd}".strip(), f"제주 {store['name']}"]
    if short != store["name"]:
        candidates.insert(1, f"{short} {emd}".strip())
    queries, result = [], None
    for q in candidates:
        queries.append(q)
        r = judge(store, search(q))
        if result is None or r["status"] == 1 or (result["status"] == 0 and r["status"] == 2):
            result = r
        if result["status"] == 1:
            break
    # 인허가 상호가 길어 못 찾았으면 앞부분만으로 검색 ('온정메밀앤돈카츠' → '온정메밀'). 주소가 같아야 등록으로 인정
    core = re.sub(r"[^가-힣A-Za-z0-9]", "", base_name(store["name"]))
    if result["status"] != 1 and len(core) >= 5:
        q = f"{core[:4]} {emd}".strip()
        queries.append(q)
        for it in search(q):
            same_addr = (road_key(store.get("addr_road")) and road_key(store.get("addr_road")) == road_key(it.get("roadAddress"))) or                         (jibun_key(store.get("addr_jibun")) and jibun_key(store.get("addr_jibun")) == jibun_key(it.get("address")))
            ns = name_score(store["name"], it["title"])
            if same_addr and (ns >= 45 or _norm_name(it["title"]) in _norm_name(store["name"])):
                result = {"status": 1, "name_score": ns, "addr_match": True, "item": it}
                break
    it = result["item"] or {}
    row = {
        "store_id": store["store_id"],
        "status": result["status"],
        "naver_title": it.get("title"),
        "naver_category": it.get("category"),
        "naver_road": it.get("roadAddress"),
        "naver_jibun": it.get("address"),
        "lat": _coord(it.get("mapy")) if result["status"] == 1 else None,
        "lng": _coord(it.get("mapx")) if result["status"] == 1 else None,
        "name_score": result["name_score"],
        "addr_match": int(result["addr_match"]),
        "queries": " | ".join(queries),
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }
    save(row)
    return row


_write_lock = __import__("threading").Lock()


def save(row: dict):
    with _write_lock, db.connect() as con:  # 여러 스레드가 동시에 쓰지 않게
        con.execute(DDL)
        con.execute(
            f"INSERT OR REPLACE INTO naver_check ({','.join(row)}) VALUES ({','.join('?' * len(row))})",
            list(row.values()),
        )
        listed = {1: 1, 0: 0}.get(row["status"])  # 확인 필요는 NULL로 둔다
        con.execute(
            "UPDATE stores SET naver_listed=?, lat=coalesce(?, lat), lng=coalesce(?, lng) WHERE store_id=?",
            [listed, row["lat"], row["lng"], row["store_id"]],
        )


# ---------- Agent 도구 ----------

def check_naver_listed(store_id: int) -> dict:
    """가게(store_id)가 네이버 지도에 등록돼 있는지 확인한다. 이미 확인한 가게는 저장된 결과를 쓴다."""
    try:
        cached = db.rows("SELECT * FROM naver_check WHERE store_id=?", [store_id])
    except Exception:
        cached = []
    if cached:
        row, fresh = cached[0], False
    else:
        stores = db.rows("SELECT store_id, name, emd, addr_road, addr_jibun FROM stores WHERE store_id=?", [store_id])
        if not stores:
            return {"error": f"store_id {store_id} 가게가 없음. find_store로 먼저 찾을 것."}
        try:
            row, fresh = check_store(stores[0]), True
        except NaverError as e:
            return {"error": f"네이버 검색 실패: {e}"}
    status = STATUS[row["status"]]
    return {
        "store_id": store_id,
        "naver_status": status,
        "naver_match": {
            "title": row["naver_title"], "category": row["naver_category"], "road_address": row["naver_road"],
        } if row["naver_title"] else None,
        "name_score": row["name_score"],
        "address_match": bool(row["addr_match"]),
        "checked_at": row["checked_at"],
        "from_cache": not fresh,
        "next_step": {
            "미등록 후보": "사장님께 네이버 스마트플레이스 등록을 권하고, 소개글·메뉴판 초안을 save_draft로 만들어 드릴 수 있음",
            "확인 필요": "네이버에 비슷한 가게가 있으나 상호나 주소가 다름. 사장님께 상호 변경·이전 여부를 여쭤볼 것",
            "등록": "이미 네이버 지도에 있음",
        }[status],
        "method": "네이버 지역 검색 결과와 상호 유사도·주소(도로명+건물번호/지번) 일치로 판별. 검색어 차이로 놓칠 수 있어 '미등록 후보'로 표기",
        "sources": db.cite("stores") + ["네이버 지역 검색 API (NAVER API HUB)"],
    }
