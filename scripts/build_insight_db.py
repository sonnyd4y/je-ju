"""허브 원본 CSV를 전처리해 분석용 테이블을 data/processed/jeju.db 에 만든다.

만드는 테이블 (원본 ID)
  meal_time_pattern   시간대·성별·연령별 외식 이용자 비율, 2019년 기준 (490)  ← 결정 D-01
  card_time           시간대별 카드 이용금액, 2019년 vs 최근 12개월, 손님 구분별 (502)
  time_recent_factor  시간대별 최근 보정 계수 = 최근 비율 / 2019 비율 (502)
  dow_factor          요일별 하루 평균 카드 이용건수 계수, 최근 12개월 (504)
  menu_sales          메뉴 분류별 외식업 매출, 연도별 (495)
  card_food_customer  음식점 업종별 손님 구성 (도민/관광객/외국인 × 성별), 최근 12개월 (1048)
  pop_daily           읍면동·일별 거주/근무/방문 인구 (583)
  pop_profile         읍면동별 성별·연령 평균 인구 (583)
  sight_monthly       관광지별 월 유입자 수, 내국인/외국인 (591, 592)
  wifi_monthly        와이파이 장소별 월 사용자 수, 장소명 정리 (568)
  reviews             구글 음식점 리뷰, 작성자 정보 삭제 (903)
  place_ratings       구글 평점 월별 추이 (906)

사용법: python scripts/build_insight_db.py
"""
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
DB = ROOT / "data/processed/jeju.db"
sys.stdout.reconfigure(encoding="utf-8")

# 490 시간대 → 502 시간대 구분 (502 시간대 정의가 공개되지 않아 근사 매핑. 한계로 기재)
SLOT_TO_CARD = {
    "00~06": "밤", "06~09": "오전", "09~12": "오전", "12~15": "점심",
    "15~18": "오후", "18~21": "저녁", "21~24": "밤",
}
USER_GROUP = {
    "제주도민": "도민", "내국인": "내국인 관광객",
    "일본": "외국인", "중국": "외국인", "동남아": "외국인", "기타외국": "외국인",
}
FOOD_BIZ = [
    "한식 음식점업", "중식 음식점업", "일식 음식점업", "서양식 음식점업", "기타 외국식 음식점업",
    "피자 햄버거 샌드위치 및 유사 음식점업", "기타 주점업", "일반유흥 주점업",
]
WEEKDAYS = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


def read_csv(path, **kw):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str, **kw)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 알 수 없음: {path}")


def one(i, pattern="*.csv"):
    files = [p for p in (RAW / str(i)).glob(pattern) if p.is_file()]
    if not files:
        raise FileNotFoundError(f"data/raw/{i}/{pattern} 없음")
    return files[0]


def last_months(ym: pd.Series, n=12):
    months = sorted(ym.unique())[-n:]
    return ym.isin(months), months


# ---------- 490 / 502 / 504 : 시간·요일 패턴 ----------

def meal_time_pattern():
    d = read_csv(one(490))
    d["user_count"] = pd.to_numeric(d["user_count"])
    d = d[d.base_year_month.str.startswith("2019") & (d.time_range != "기타")]
    g = d.groupby(["time_range", "sex", "age_range"], as_index=False)["user_count"].sum()
    g["share"] = g.user_count / g.user_count.sum()
    g["card_time"] = g.time_range.map(SLOT_TO_CARD)
    return g.rename(columns={"user_count": "users_2019"})


def card_time():
    d = read_csv(one(502))
    d["amount"] = pd.to_numeric(d["use_amout_by_million"])
    d["user_group"] = d.user_type.map(USER_GROUP)
    d = d.dropna(subset=["user_group"])
    recent, months = last_months(d.base_year_month)
    d["period"] = None
    d.loc[d.base_year_month.str.startswith("2019"), "period"] = "2019"
    d.loc[recent, "period"] = "recent"
    g = d.dropna(subset=["period"]).groupby(["period", "user_group", "time_type"], as_index=False)["amount"].sum()
    g["share"] = g.amount / g.groupby(["period", "user_group"]).amount.transform("sum")
    g.attrs["recent"] = f"{months[0]}~{months[-1]}"

    p = g.pivot_table(index=["user_group", "time_type"], columns="period", values="share").reset_index()
    p["factor"] = (p["recent"] / p["2019"]).round(3)
    return g.rename(columns={"amount": "amount_million"}), p[["user_group", "time_type", "factor"]]


def dow_factor():
    d = read_csv(one(504))
    d["use_count"] = pd.to_numeric(d["use_count"])
    recent, months = last_months(d.base_year_month)
    d = d[recent]
    g = d.groupby(["base_year_month", "day_of_week"], as_index=False)["use_count"].sum()

    # 그 달에 해당 요일이 몇 번 있었는지로 나눠 '하루 평균'으로 만든다 (공휴일은 제외하고 계산)
    def n_days(row):
        if row.day_of_week not in WEEKDAYS:
            return None
        p = pd.Period(row.base_year_month, freq="M")
        days = pd.date_range(p.start_time, p.end_time, freq="D")
        return int((days.dayofweek == WEEKDAYS.index(row.day_of_week)).sum())

    g["days"] = g.apply(n_days, axis=1)
    g = g.dropna(subset=["days"])
    g["per_day"] = g.use_count / g.days
    out = g.groupby("day_of_week", as_index=False)["per_day"].mean()
    out["factor"] = (out.per_day / out.per_day.mean()).round(3)
    out["order"] = out.day_of_week.map(WEEKDAYS.index)
    out.attrs["period"] = f"{months[0]}~{months[-1]}"
    return out.sort_values("order").drop(columns="order")


# ---------- 495 / 1048 : 메뉴·손님 구성 ----------

def menu_sales():
    d = read_csv(one(495))
    d["amount"] = pd.to_numeric(d["sale_amount_by_million"])
    d["year"] = d.base_year_month.str[:4]
    g = d.groupby(["year", "menu_name"], as_index=False)["amount"].sum()
    g["share"] = g.amount / g.groupby("year").amount.transform("sum")
    return g.rename(columns={"amount": "amount_million"})


def card_food_customer():
    d = read_csv(one(1048))
    for c in ("user_count", "use_count", "use_amount"):
        d[c] = pd.to_numeric(d[c])
    d = d[d.biz_nm.isin(FOOD_BIZ)]
    d["user_group"] = d.user_type.map(USER_GROUP)
    d = d.dropna(subset=["user_group"])
    recent, months = last_months(d.base_year_month)
    g = d[recent].groupby(["biz_nm", "user_group", "sex"], as_index=False)[["user_count", "use_count", "use_amount"]].sum()
    g.attrs["period"] = f"{months[0]}~{months[-1]}"
    return g


# ---------- 583 : 유동인구 ----------

def population():
    d = read_csv(one(583, "583_api.csv"))
    for c in ("resdPop", "workPop", "visitPop"):
        d[c] = pd.to_numeric(d[c])
    d["date"] = pd.to_datetime(d.baseDate, format="%Y%m%d").dt.strftime("%Y-%m-%d")
    daily = d.groupby(["date", "city", "emd"], as_index=False)[["resdPop", "workPop", "visitPop"]].sum()
    daily.columns = ["date", "city", "emd", "resident", "worker", "visitor"]
    daily["weekday"] = pd.to_datetime(daily.date).dt.dayofweek.map(lambda i: WEEKDAYS[i])

    prof = d.groupby(["city", "emd", "gender", "ageGroup", "date"], as_index=False)[["resdPop", "workPop", "visitPop"]].sum()
    prof = prof.groupby(["city", "emd", "gender", "ageGroup"], as_index=False)[["resdPop", "workPop", "visitPop"]].mean().round()
    prof.columns = ["city", "emd", "gender", "age_group", "resident", "worker", "visitor"]
    return daily, prof


# ---------- 591 / 592 : 관광지 ----------

def sight_monthly():
    frames = []
    for i, kind in ((591, "domestic"), (592, "foreign")):
        d = read_csv(one(i, f"{i}_api.csv"))
        d["users"] = pd.to_numeric(d["userCnt"])
        g = d.groupby(["dtYearMonth", "sightsName"], as_index=False)["users"].sum()
        g["kind"] = kind
        frames.append(g)
    d = pd.concat(frames)
    p = d.pivot_table(index=["dtYearMonth", "sightsName"], columns="kind", values="users", aggfunc="sum").reset_index()
    p.columns.name = None
    return p.rename(columns={"dtYearMonth": "ym", "sightsName": "sight"})


# ---------- 568 : 와이파이 ----------

def clean_place(name: str):
    """'칠십리공원_A ＃2-2' → '칠십리공원', '버스정류소_남원읍사무소[남]' → '남원읍사무소' (type=버스정류소)."""
    s = str(name).strip()
    kind = "장소"
    if s.startswith("버스정류소_"):
        kind, s = "버스정류소", s[len("버스정류소_"):]
        s = re.sub(r"\[[^\]]*\]$", "", s)          # [남] [동] 같은 방향 표시
    s = re.split(r"\s*[#＃]", s)[0]                  # AP 번호
    s = re.sub(r"_[A-Za-z0-9]+$", "", s)             # _A, _1 같은 접미어
    s = re.sub(r"\s*\d+$", "", s) if not re.fullmatch(r"\D*\d+코스", s) else s  # 남원읍1 → 남원읍
    return s.strip() or str(name).strip(), kind


def wifi_monthly():
    d = read_csv(one(568), usecols=["base_year_month", "wifi_place_name", "user_count"])
    # 원본에 "1012`" 처럼 숫자 뒤 오타 문자가 섞인 값이 있어 숫자만 남긴다
    d["user_count"] = pd.to_numeric(d["user_count"].str.replace(r"\D", "", regex=True), errors="coerce").fillna(0)
    names = pd.Series(d.wifi_place_name.unique())
    m = pd.DataFrame(names.map(clean_place).tolist(), columns=["place", "place_type"])
    m["wifi_place_name"] = names
    d = d.merge(m, on="wifi_place_name")
    g = d.groupby(["base_year_month", "place", "place_type"], as_index=False)["user_count"].sum()
    return g.rename(columns={"base_year_month": "ym", "user_count": "users"})


# ---------- 903 / 906 : 리뷰 ----------

def reviews():
    frames = []
    for f in sorted((RAW / "903").glob("*.csv")):
        d = read_csv(f)
        # 개인정보: 작성자 이름(name), 등급(level), 작성자 리뷰수(review), 사진수(photo), 사진 URL(imeges) 삭제
        d = d[["title", "type", "time", "stars", "contents"]]
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d.columns = ["store", "price_level", "time_text", "stars", "contents"]
    d["stars"] = pd.to_numeric(d.stars, errors="coerce")
    d["contents"] = d.contents.fillna("").str.strip()
    d.insert(0, "review_id", range(1, len(d) + 1))
    d["source"] = "google_2021"
    return d


def place_ratings():
    d = read_csv(one(906, "*.csv"), header=None)
    d.columns = ["place", "metric", "rating", "count", "date", "weekday"]
    d = d.drop(columns="metric")
    d["rating"] = pd.to_numeric(d.rating, errors="coerce")
    d["count"] = pd.to_numeric(d["count"], errors="coerce")
    d["date"] = pd.to_datetime(d.date, format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    return d


def main():
    tables, meta = {}, []

    def add(name, df, source, period, note=""):
        tables[name] = df
        meta.append({"table": name, "source": source, "period": period, "rows": len(df), "note": note})
        print(f"  {name:<20} {len(df):>9,}행  ({source}, {period})")

    def step_meal():
        add("meal_time_pattern", meal_time_pattern(), "490", "2019", "코로나 이전 기준 (D-01)")

    def step_card():
        g, f = card_time()
        add("card_time", g, "502", f"2019 vs {g.attrs['recent']}")
        add("time_recent_factor", f, "502", f"{g.attrs['recent']} / 2019")

    def step_dow():
        x = dow_factor()
        add("dow_factor", x, "504", x.attrs["period"], "공휴일 제외, 요일 수로 나눈 하루 평균")

    def step_menu():
        x = menu_sales()
        add("menu_sales", x, "495", f"{x.year.min()}~{x.year.max()}")

    def step_customer():
        x = card_food_customer()
        add("card_food_customer", x, "1048", x.attrs["period"], "음식점·주점 업종만")

    def step_pop():
        daily, prof = population()
        period = f"{daily.date.min()}~{daily.date.max()}"
        add("pop_daily", daily, "583", period)
        add("pop_profile", prof, "583", period, "일평균")

    def step_sight():
        x = sight_monthly()
        add("sight_monthly", x, "591,592", f"{x.ym.min()}~{x.ym.max()}")

    def step_wifi():
        x = wifi_monthly()
        add("wifi_monthly", x, "568", f"{x.ym.min()}~{x.ym.max()}", "장소명 AP번호 제거 후 합산")

    def step_reviews():
        add("reviews", reviews(), "903", "2021", "작성자 정보 삭제")
        x = place_ratings()
        add("place_ratings", x, "906", f"{x.date.min()}~{x.date.max()}")

    print("전처리:")
    for step in (step_meal, step_card, step_dow, step_menu, step_customer, step_pop, step_sight, step_wifi, step_reviews):
        try:
            step()
        except FileNotFoundError as e:
            print(f"  {step.__name__} 건너뜀: {e}")

    with sqlite3.connect(DB) as con:
        for name, df in tables.items():
            df.to_sql(name, con, if_exists="replace", index=False)
        pd.DataFrame(meta).to_sql("data_sources", con, if_exists="replace", index=False)
        con.execute("CREATE INDEX IF NOT EXISTS ix_pop_emd ON pop_daily(emd, date)")
        con.execute("CREATE INDEX IF NOT EXISTS ix_wifi_place ON wifi_monthly(place)")
    print(f"저장: {DB}")


if __name__ == "__main__":
    main()
