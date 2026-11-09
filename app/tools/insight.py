"""지역 분석 도구: area_insight, predict_crowd, resident_balance.

혼잡 예측은 실시간이 아니라 과거 패턴 기반 추정이다 (결정 D-01, 개발계획 7-2).

  혼잡 지수(지역, 요일, 시간대) =
      요일 계수     (583: 이 지역 해당 요일 방문인구 / 이 지역 평균)
    × 시간대 계수   (490 2019년 외식 시간대 비율 × 502 최근 보정, 지역의 관광객 비중으로 가중)
    × 관광 밀도     (583: 방문인구 / 거주인구, 제주 전체 중앙값 대비)
  → 제주 전체 (지역 × 요일 × 시간대) 분포의 하위 40% 한산 / 40~80% 보통 / 상위 20% 붐빔
"""
from functools import lru_cache

import pandas as pd

from app.data import db, regions
from app.tools import forecast

SLOTS = ["09~12", "12~15", "15~18", "18~21", "21~24"]
SLOT_LABELS = {"09~12": "오전 9~12시", "12~15": "점심 12~15시", "15~18": "오후 15~18시", "18~21": "저녁 18~21시", "21~24": "밤 21~24시"}
SLOT_ALIASES = {
    "아침": "09~12", "오전": "09~12", "브런치": "09~12",
    "점심": "12~15", "낮": "12~15",
    "오후": "15~18", "간식": "15~18",
    "저녁": "18~21",
    "밤": "21~24", "야식": "21~24", "늦은저녁": "21~24",
}
WEEKDAYS = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
LEVELS = ["한산", "보통", "붐빔"]


def _slot(s: str) -> str | None:
    s = (s or "").replace(" ", "")
    if s in SLOTS:
        return s
    if s in SLOT_ALIASES:
        return SLOT_ALIASES[s]
    # "12시", "19:30" → 시간대
    digits = "".join(ch for ch in s if ch.isdigit())[:2]
    if digits:
        h = int(digits)
        if "오후" in s or "저녁" in s or "밤" in s:
            h = h + 12 if h < 12 else h
        for sl in SLOTS:
            a, b = map(int, sl.split("~"))
            if a <= h < b:
                return sl
    return None


def _weekday(s: str) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    for w in WEEKDAYS:
        if s in (w, w[0], w[:2]):
            return w
    try:
        return WEEKDAYS[pd.Timestamp(s).dayofweek]
    except Exception:
        return None


# ---------- 공통 데이터 ----------

@lru_cache(maxsize=1)
def _pop() -> pd.DataFrame:
    return db.query("SELECT date, city, emd, resident, worker, visitor, weekday FROM pop_daily")


def _region_daily(r: dict) -> pd.DataFrame:
    p = _pop()
    p = p[(p.city == r["city"]) & p.emd.isin(r["admin"])]
    return p.groupby(["date", "weekday"], as_index=False)[["resident", "worker", "visitor"]].sum()


@lru_cache(maxsize=1)
def _region_table() -> pd.DataFrame:
    """행정동별 일평균 인구, 관광 밀도(방문/거주), 요일별 방문 계수."""
    p = _pop()
    avg = p.groupby(["city", "emd"], as_index=False)[["resident", "worker", "visitor"]].mean()
    avg["visit_ratio"] = avg.visitor / avg.resident
    avg["pressure"] = avg.visit_ratio / avg.visit_ratio.median()
    avg["ratio_pct"] = avg.visit_ratio.rank(pct=True)
    return avg


@lru_cache(maxsize=4)
def _slot_shares(tourist_weight: float) -> dict[str, float]:
    """식당 시간대 비율. 2019 외식 패턴(490)에 최근 카드 보정(502)을 도민/관광객 비중대로 섞어 곱한다."""
    base = db.query("SELECT time_range, card_time, sum(share) share FROM meal_time_pattern GROUP BY 1, 2")
    f = db.query("SELECT user_group, time_type, factor FROM time_recent_factor")
    f = f.pivot(index="time_type", columns="user_group", values="factor")
    w = max(0.0, min(1.0, tourist_weight))
    base["factor"] = base.card_time.map(lambda t: w * f.loc[t, "내국인 관광객"] + (1 - w) * f.loc[t, "도민"])
    base["adj"] = base.share * base.factor
    base["adj"] = base.adj / base.adj.sum()
    return dict(zip(base.time_range, base.adj.round(4)))


def _mix(res: float, wrk: float, vis: float) -> dict:
    """583 값은 하루 누적 집계라 사람 수가 아니다. 구성비로만 보여준다."""
    tot = res + wrk + vis
    return {"거주": f"{res / tot:.0%}", "근무": f"{wrk / tot:.0%}", "방문": f"{vis / tot:.0%}"}


def _tourist_weight(visitor: float, resident: float) -> float:
    return round(visitor / (visitor + resident), 2) if visitor + resident else 0.5


@lru_cache(maxsize=1)
def _weekday_table() -> pd.DataFrame:
    """행정동 × 요일 평균 방문인구."""
    return _pop().groupby(["city", "emd", "weekday"]).visitor.mean()


def _crowd_index(city: str, emds: list[str], weekday: str, slot: str, day_rel: float | None = None) -> float:
    """day_rel: 그 날 방문이 평소의 몇 배인지 (날짜를 주면 예측 모델 값, 없으면 요일 평균)."""
    t = _region_table()
    rows = t[(t.city == city) & t.emd.isin(emds)]
    if day_rel is None:
        wt = _weekday_table()
        day_rel = sum(wt[(city, e, weekday)] for e in emds) / rows.visitor.sum()
    vis, res = rows.visitor.sum(), rows.resident.sum()
    pressure = (vis / res) / t.visit_ratio.median()
    shares = _slot_shares(round(_tourist_weight(vis, res), 1))
    slot_rel = shares[slot] / (1 / len(SLOTS))
    return float(day_rel * slot_rel * pressure)


@lru_cache(maxsize=1)
def _crowd_thresholds() -> tuple[float, float]:
    """제주 전체 (행정동 × 요일 × 시간대) 혼잡 지수의 40%, 80% 분위값."""
    t = _region_table().set_index(["city", "emd"])
    wt = _weekday_table().reset_index()
    wt = wt.join(t[["visitor", "resident", "pressure"]], on=["city", "emd"], rsuffix="_avg")
    wt["day_rel"] = wt.visitor / wt.visitor_avg
    wt["tw"] = [round(_tourist_weight(v, r), 1) for v, r in zip(wt.visitor_avg, wt.resident)]
    vals = []
    for s in SLOTS:
        slot_rel = wt.tw.map(lambda w: _slot_shares(w)[s] * len(SLOTS))
        vals.append(wt.day_rel * slot_rel * wt.pressure)
    q = pd.concat(vals).quantile([0.4, 0.8])
    return float(q.iloc[0]), float(q.iloc[1])


def _level(idx: float) -> str:
    lo, hi = _crowd_thresholds()
    return LEVELS[0] if idx < lo else LEVELS[1] if idx < hi else LEVELS[2]


def _resolve(region: str):
    r = regions.resolve(region)
    if not r:
        return None, {"error": f"'{region}' 지역을 찾지 못함. 읍·면·동 이름(예: 애월읍, 연동, 중문동)으로 다시 요청할 것."}
    return r, None


# ---------- 도구 ----------

def predict_crowd(region: str, weekday: str = "", time_slot: str = "") -> dict:
    """지역의 요일·시간대별 식당 혼잡 등급(한산/보통/붐빔)을 과거 패턴으로 예측한다."""
    r, err = _resolve(region)
    if err:
        return err
    wd = _weekday(weekday)
    sl = _slot(time_slot)
    days = [wd] if wd else WEEKDAYS
    slots = [sl] if sl else SLOTS

    # 날짜를 주면 수요 예측 모델(공휴일·연휴·계절 반영)로 그 날의 방문 수준을 구한다
    date, day_rel, day_note = _as_date(weekday), None, None
    if date:
        days = [WEEKDAYS[pd.Timestamp(date).dayofweek]]
        day_rel = forecast.predict_day_ratio(r["city"], r["admin"], date)
        if day_rel is None and forecast.is_holiday(date):
            days, day_note = ["일요일"], "공휴일이라 일요일 패턴으로 예측 (공휴일은 학습 표본이 적어 모델 대신 사용)"
        elif day_rel is not None:
            day_note = f"수요 예측 모델: 이 날 방문 인구는 이 동네 평소의 {day_rel:.2f}배로 예측"

    table = []
    for d in days:
        for s in slots:
            idx = _crowd_index(r["city"], r["admin"], d, s, day_rel)
            row = {"weekday": d, "time_slot": SLOT_LABELS[s], "level": _level(idx), "_idx": idx}
            if date:
                row["date"] = date
            table.append(row)
    # 지수 값은 내부 정렬용. 응답에서는 빼서 '평소의 몇 배'처럼 잘못 해석되지 않게 한다
    ranked = sorted(table, key=lambda x: x["_idx"])
    for rank, row in enumerate(ranked, 1):
        row["quiet_rank"] = rank
    for row in table:
        row.pop("_idx")
    best = ranked[:3]
    return {
        "region": r["label"],
        "admin_areas": r["admin"],
        "forecast": table,
        "quietest": best,
        **({"date": date, "day_outlook": day_note} if date else {}),
        "how_to_read": "level은 제주 전체 지역·요일·시간대와 비교한 등급. quiet_rank 1이 이 표에서 가장 한산함. "
                       "'평소의 몇 배' 같은 배수로 말하지 말 것.",
        "method": "과거 패턴 기반 추정 (실시간 아님). 그 날 방문 수준(날짜를 주면 수요 예측 모델, 아니면 요일 평균, 583) × "
                  "식당 시간대 비율(490 2019년, 502 최근 보정) × 관광 밀도(583). "
                  "등급은 제주 전체 지역·요일·시간대 분포 기준 하위 40% 한산, 상위 20% 붐빔. "
                  + _model_note(),
        "sources": db.cite("pop_daily", "meal_time_pattern", "time_recent_factor"),
    }


def _as_date(s: str) -> str | None:
    """'2026-11-14', '11월 14일', '11/14' → 'YYYY-MM-DD'. 요일만 주면 None."""
    import re
    s = (s or "").strip()
    m = re.search(r"(\d{4})[-./년 ]\s*(\d{1,2})[-./월 ]\s*(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.search(r"(\d{1,2})\s*[월/.-]\s*(\d{1,2})", s)
        if not m:
            return None
        mo, d = map(int, m.groups())
        today = pd.Timestamp.today()
        y = today.year + (1 if (mo, d) < (today.month, today.day) else 0)
    try:
        return pd.Timestamp(year=y, month=mo, day=d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _model_note() -> str:
    m = forecast.metrics()
    if not m:
        return ""
    return (f"수요 예측 모델 검증({m['test']}): 오차 {m['mape']['model']:.0%} (요일 평균 {m['mape']['weekday_average']:.0%}), "
            f"등급 일치 {m['level_accuracy']['model']:.0%} (요일 평균 {m['level_accuracy']['weekday_average']:.0%}).")


def resident_balance(region: str) -> dict:
    """지역의 거주인구 대비 방문인구 비율로 도민 생활권 과밀 여부를 판단한다."""
    r, err = _resolve(region)
    if err:
        return err
    t = _region_table()
    rows = t[(t.city == r["city"]) & t.emd.isin(r["admin"])]
    vis, res, wrk = rows.visitor.sum(), rows.resident.sum(), rows.worker.sum()
    ratio = vis / res
    pct = float((t.visit_ratio <= ratio).mean())
    level = "과밀" if pct >= 0.8 else "주의" if pct >= 0.6 else "여유"
    weight = {"과밀": 0.5, "주의": 0.8, "여유": 1.0}[level]
    return {
        "region": r["label"],
        "population_mix": _mix(res, wrk, vis),
        "visitor_per_resident": round(float(ratio), 2),
        "rank_percentile": round(pct * 100),
        "level": level,
        "recommend_weight": weight,
        "note": f"제주 {len(t)}개 읍면동 중 방문/거주 비율 상위 {100 - round(pct * 100)}%. "
                "과밀 지역은 관광객 추천 가중치를 낮춰 도민 생활권을 보호한다.",
        "sources": db.cite("pop_daily"),
    }


def area_insight(region: str, category: str = "") -> dict:
    """지역 상권 요약: 방문객 구성, 요일·시간대 패턴, 가게 현황, 제주 외식 트렌드."""
    r, err = _resolve(region)
    if err:
        return err
    daily = _region_daily(r)
    if daily.empty:
        return {"error": f"{r['label']} 유동인구 데이터가 없음"}
    vis, res, wrk = daily.visitor.mean(), daily.resident.mean(), daily.worker.mean()

    # 방문객 성별·연령 상위
    prof = db.query(
        f"SELECT gender, age_group, sum(visitor) v FROM pop_profile WHERE city=? AND emd IN ({','.join('?' * len(r['admin']))}) "
        "GROUP BY 1, 2 ORDER BY v DESC",
        [r["city"], *r["admin"]],
    )
    prof["share"] = prof.v / prof.v.sum()
    top_visitors = [f"{g} {a} {s:.0%}" for g, a, s in prof[["gender", "age_group", "share"]].head(3).values]

    wd = daily.groupby("weekday").visitor.mean()
    weekday_factor = {w: round(float(wd[w] / wd.mean()), 2) for w in WEEKDAYS if w in wd}
    tw = _tourist_weight(vis, res)
    slots = _slot_shares(round(tw, 1))

    # 가게 현황
    ph = ",".join("?" * len(r["legal"]))
    asof = db.rows("SELECT max(open_date) d FROM stores")[0]["d"]  # 인허가 데이터 기준일
    st = db.rows(
        f"SELECT count(*) n, sum(open_date >= date(?, '-1 year')) new_1y FROM stores "
        f"WHERE status LIKE '영업%' AND city=? AND emd IN ({ph})",
        [asof, r["city"], *r["legal"]],
    )[0]
    cats = db.rows(
        f"SELECT category, count(*) n FROM stores WHERE status LIKE '영업%' AND city=? AND emd IN ({ph}) "
        "GROUP BY 1 ORDER BY n DESC LIMIT 5",
        [r["city"], *r["legal"]],
    )
    closed = db.rows(
        f"SELECT count(*) n FROM stores WHERE status LIKE '폐업%' AND close_date >= date(?, '-1 year') "
        f"AND city=? AND emd IN ({ph})",
        [asof, r["city"], *r["legal"]],
    )[0]["n"]

    # 제주 전체 외식 트렌드
    menu = db.rows("SELECT menu_name, share FROM menu_sales WHERE year=(SELECT max(year) FROM menu_sales) ORDER BY share DESC LIMIT 5")
    cust = db.query("SELECT user_group, sum(use_amount) a FROM card_food_customer WHERE biz_nm='한식 음식점업' GROUP BY 1")
    cust["share"] = cust.a / cust.a.sum()

    return {
        "region": r["label"],
        "admin_areas": r["admin"],
        "population_mix": _mix(res, wrk, vis),
        "visitor_per_resident": round(float(vis / res), 2),
        "tourist_weight": tw,
        "top_visitor_groups": top_visitors,
        "visitor_weekday_factor": weekday_factor,
        "busiest_day": max(weekday_factor, key=weekday_factor.get),
        "meal_time_share": {k: f"{v:.0%}" for k, v in slots.items()},
        "stores": {
            "as_of": asof,
            "open": st["n"],
            "opened_last_1y": st["new_1y"] or 0,
            "closed_last_1y": closed,
            "top_categories": {c["category"]: c["n"] for c in cats},
        },
        "jeju_trend": {
            "top_menu_sales_share": {m["menu_name"]: f"{m['share']:.0%}" for m in menu},
            "korean_restaurant_card_spend_share": {g: f"{s:.0%}" for g, s in zip(cust.user_group, cust.share)},
        },
        "notes": [
            "식당 시간대 비율은 2019년 외식업 POS 기준이며 최근 카드 데이터로 보정한 추정치임",
            "메뉴 매출·손님 구성은 제주 전체 기준 (읍면동 단위 데이터 없음)",
            "유동인구(583)는 하루 누적 집계값이라 사람 수가 아닌 구성비·비율로만 해석",
        ],
        "sources": db.cite("pop_daily", "pop_profile", "stores", "meal_time_pattern", "time_recent_factor", "menu_sales", "card_food_customer"),
    }
