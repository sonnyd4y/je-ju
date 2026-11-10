"""가게 조회 도구: find_store, search_stores (원본: 780 음식점 인허가 목록)."""
import re

from rapidfuzz import fuzz, process

from app.data import db, regions

STORE_COLS = (
    "store_id, name, biz_type, category, open_date, status, city, emd, admin_emd, "
    "addr_road, addr_jibun, area_m2, lat, lng, naver_listed"
)

# 사용자가 쓰는 말 → 인허가 업태(category)
CATEGORY_ALIASES = {
    "카페": ["커피숍", "까페", "다방", "전통찻집", "떡카페", "라이브카페", "키즈카페"],
    "커피": ["커피숍", "까페"],
    "한식": ["한식", "식육(숯불구이)", "탕류(보신용)", "냉면집"],
    "고기": ["식육(숯불구이)"],
    "흑돼지": ["식육(숯불구이)"],
    "횟집": ["횟집", "복어취급"],
    "해산물": ["횟집", "복어취급"],
    "술집": ["호프/통닭", "정종/대포집/소주방", "감성주점"],
    "치킨": ["호프/통닭", "통닭(치킨)"],
    "분식": ["분식", "김밥(도시락)"],
    "양식": ["경양식", "패밀리레스트랑"],
    "중식": ["중국식"],
    "일식": ["일식"],
    "디저트": ["과자점", "아이스크림", "떡카페"],
}
# 관광객 추천에서 빼는 업태 (식당이 아님)
NON_RESTAURANT = ["편의점", "극장", "공항", "관광호텔", "유원지", "백화점", "출장조리"]


# 해수욕장 계절음식점·마을 단체 이름의 인허가 (여름 한철 운영) — 추천·목록에서 뺀다
SEASONAL_SQL = "(name LIKE '%계절음식점%' OR name LIKE '%청년회' OR name LIKE '%부녀회%')"

def _norm_name(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", s or "")
    s = re.sub(r"(주식회사|\(주\)|㈜)", "", s)
    return re.sub(r"[\s\-_.·,]", "", s).lower()


def _name_score(a: str, b: str, **_) -> float:
    """상호 유사도. 한쪽이 다른 쪽을 포함하면 길이 비율만큼 인정 ('수'가 '거멍국수'에 높은 점수를 받지 않도록)."""
    if not a or not b:
        return 0
    base = fuzz.ratio(a, b)
    short, long_ = sorted((a, b), key=len)
    if short in long_:
        base = max(base, 100 * (0.5 + 0.5 * len(short) / len(long_)))
    return base


def _status_label(r: dict) -> str:
    return "영업 중" if str(r.get("status", "")).startswith("영업") else (r.get("status") or "알 수 없음")


def _naver_name(store_id: int) -> str | None:
    """네이버에 등록된 상호 (인허가 상호와 다를 때 표시용)."""
    try:
        n = db.rows("SELECT naver_title, status, addr_match FROM naver_check WHERE store_id=?", [store_id])
    except Exception:
        return None
    return n[0]["naver_title"] if n and (n[0]["status"] == 1 or n[0]["addr_match"]) else None


def _public(r: dict) -> dict:
    """도구 응답용 가게 정보 (주소는 도로명 우선)."""
    return {
        "store_id": r["store_id"],
        "name": r["name"],
        "category": r["category"],
        "status": _status_label(r),
        "open_date": r["open_date"],
        "region": " ".join(x for x in (r["city"], r["emd"]) if x),
        "address": r["addr_road"] or r["addr_jibun"],
        "area_m2": r["area_m2"],
        "lat": r["lat"],
        "lng": r["lng"],
        "naver_listed": {1: "등록", 0: "미등록 후보"}.get(r["naver_listed"], "미확인"),
        "naver_name": _naver_name(r["store_id"]),
    }


def find_store(name: str, address_hint: str = "", include_closed: bool = False, limit: int = 5) -> dict:
    """상호(일부 오타 허용)와 주소 일부로 인허가 DB에서 가게를 찾는다."""
    where = "" if include_closed else "WHERE status LIKE '영업%'"
    cands = db.rows(f"SELECT {STORE_COLS} FROM stores {where}")
    hint = re.sub(r"\s+", "", address_hint or "")
    if hint:
        cands = [
            c for c in cands
            if hint in re.sub(r"\s+", "", f"{c['addr_road'] or ''}{c['addr_jibun'] or ''}{c['emd'] or ''}")
        ] or cands
    key = _norm_name(name)
    names = [_norm_name(c["name"]) for c in cands]
    hits = process.extract(key, names, scorer=_name_score, limit=limit * 3)
    out = []
    for _, score, idx in hits:
        if score < 60:
            continue
        c = _public(cands[idx])
        c["match_score"] = round(score)
        out.append(c)
    out = sorted(out, key=lambda x: -x["match_score"])[:limit]
    return {
        "query": {"name": name, "address_hint": address_hint},
        "matches": out,
        "note": "match_score 90 이상이면 같은 가게일 가능성이 높음. 낮으면 사용자에게 주소로 확인할 것." if out
        else "일치하는 가게가 없음. 상호를 다르게 부르거나 아직 인허가 목록에 반영 전일 수 있음.",
        "sources": db.cite("stores"),
    }


def search_stores(
    region: str = "",
    category: str = "",
    opened_after: str = "",
    unlisted_only: bool = False,
    keyword: str = "",
    limit: int = 20,
) -> dict:
    """지역·업태·개업일·네이버 미등록 여부로 영업 중인 가게 목록을 조회한다."""
    sql = [f"SELECT {STORE_COLS} FROM stores WHERE status LIKE '영업%' AND NOT {SEASONAL_SQL}"]
    params: list = []
    label = "제주 전체"
    if region:
        r = regions.resolve(region)
        if not r:
            return {"error": f"'{region}' 지역을 찾지 못함. 읍·면·동 이름으로 다시 요청할 것."}
        label = r["label"]
        sql.append(f"AND city = ? AND emd IN ({','.join('?' * len(r['legal']))})")
        params += [r["city"], *r["legal"]]
    if category:
        cats = CATEGORY_ALIASES.get(category.strip(), [category.strip()])
        sql.append(f"AND category IN ({','.join('?' * len(cats))})")
        params += cats
    else:
        sql.append(f"AND coalesce(category,'') NOT IN ({','.join('?' * len(NON_RESTAURANT))})")
        params += NON_RESTAURANT
    if opened_after:
        sql.append("AND open_date >= ?")
        params.append(opened_after)
    if unlisted_only:
        sql.append("AND naver_listed = 0")
    if keyword:
        sql.append("AND name LIKE ?")
        params.append(f"%{keyword}%")

    base = " ".join(sql)
    total = db.rows(f"SELECT count(*) n FROM ({base})", params)[0]["n"]
    # 좌표가 있는 가게, 최근 개업 가게를 먼저
    found = db.rows(base + " ORDER BY (lat IS NULL), open_date DESC LIMIT ?", [*params, max(1, min(limit, 50))])
    by_cat = db.rows(f"SELECT category, count(*) n FROM ({base}) GROUP BY category ORDER BY n DESC LIMIT 8", params)
    return {
        "region": label,
        "total": total,
        "by_category": {c["category"]: c["n"] for c in by_cat},
        "stores": [_public(r) for r in found],
        "note": "네이버 등록 여부는 확인한 가게만 표시됨 (미확인 다수)." if unlisted_only else "",
        "sources": db.cite("stores"),
    }
