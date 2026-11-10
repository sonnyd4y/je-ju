"""방문 수요 예측 모델 (오픈소스 머신러닝: scikit-learn HistGradientBoosting).

읍면동·날짜별 방문인구(583)를 '그 동네 평균 대비 비율'로 예측한다.
특징: 요일, 공휴일, 연휴 앞뒤(징검다리 포함), 월·계절, 동네.
기존 방식(동네별 요일 평균)과 같은 기간으로 비교해 정확도를 기록한다.

  학습: python scripts/train_demand.py   → data/processed/demand_model.joblib, demand_metrics.json
  사용: predict_day_ratio(city, emds, "2026-11-14")  → 그 날 방문이 평소의 몇 배인지
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from app.data import db

MODEL_PATH = db.ROOT / "data/processed/demand_model.joblib"
METRICS_PATH = db.ROOT / "data/processed/demand_metrics.json"


def _holidays(years):
    return _holidays_cached(tuple(int(y) for y in years))


@lru_cache(maxsize=16)
def _holidays_cached(years: tuple):
    import holidays
    return holidays.KR(years=years)


def features(dates: pd.Series, emd_codes: pd.Series) -> pd.DataFrame:
    """날짜·동네 → 모델 입력."""
    d = pd.to_datetime(dates)
    hol = _holidays(sorted(set(d.dt.year) | {d.dt.year.max() + 1}))
    is_hol = d.map(lambda x: x in hol).astype(int)
    off = ((d.dt.dayofweek >= 5) | (is_hol == 1)).astype(int)  # 쉬는 날
    # 연휴 길이: 이 날을 포함해 이어지는 쉬는 날 수 (징검다리 포착)
    def run_len(x):
        if not (x.dayofweek >= 5 or x in hol):
            return 0
        n, y = 1, x - pd.Timedelta(days=1)
        while y.dayofweek >= 5 or y in hol:
            n, y = n + 1, y - pd.Timedelta(days=1)
        y = x + pd.Timedelta(days=1)
        while y.dayofweek >= 5 or y in hol:
            n, y = n + 1, y + pd.Timedelta(days=1)
        return n
    nxt = d + pd.Timedelta(days=1)
    prv = d - pd.Timedelta(days=1)
    doy = d.dt.dayofyear
    return pd.DataFrame({
        "emd": emd_codes.values,
        "dow": d.dt.dayofweek.values,
        "holiday": is_hol.values,
        "off": off.values,
        "long_weekend": d.map(run_len).values,
        "before_off": ((nxt.dt.dayofweek >= 5) | nxt.map(lambda x: x in hol)).astype(int).values,
        "after_off": ((prv.dt.dayofweek >= 5) | prv.map(lambda x: x in hol)).astype(int).values,
        "month": d.dt.month.values,
        "doy_sin": np.sin(2 * np.pi * doy / 365.25).values,
        "doy_cos": np.cos(2 * np.pi * doy / 365.25).values,
    })


def training_frame() -> pd.DataFrame:
    p = db.query("SELECT date, city, emd, visitor FROM pop_daily")
    p["key"] = p.city + " " + p.emd
    p["ratio"] = p.visitor / p.groupby("key").visitor.transform("mean")
    return p


@lru_cache(maxsize=1)
def _load():
    import joblib
    if not MODEL_PATH.exists():
        return None
    return joblib.load(MODEL_PATH)


def is_holiday(date: str) -> bool:
    d = pd.Timestamp(date)
    return d in _holidays([d.year])


@lru_cache(maxsize=64)
def _day_preds(date: str) -> dict[str, float]:
    """그 날 모든 동네를 한 번에 예측해 둔다 (지도처럼 동네 42곳을 연달아 물을 때 한 번만 계산)."""
    bundle = _load()
    keys = list(bundle["codes"])
    X = features(pd.Series([date] * len(keys)), pd.Series([bundle["codes"][k] for k in keys]))
    return dict(zip(keys, np.exp(bundle["model"].predict(X)).tolist()))


def predict_day_ratio(city: str, emds: list[str], date: str) -> float | None:
    """그 날 방문인구가 동네 평소(평균)의 몇 배일지. 모델이 없거나 공휴일이면 None (호출 쪽에서 요일 평균 사용)."""
    bundle = _load()
    if not bundle or is_holiday(date):
        return None
    model, codes, base = bundle["model"], bundle["codes"], bundle["base"]
    keys = [f"{city} {e}" for e in emds if f"{city} {e}" in codes]
    if not keys:
        return None
    day = _day_preds(date)
    pred = np.array([day[k] for k in keys])
    w = np.array([base[k] for k in keys])  # 동네 규모로 가중
    return float((pred * w).sum() / w.sum())


def metrics() -> dict:
    return json.loads(METRICS_PATH.read_text(encoding="utf-8")) if METRICS_PATH.exists() else {}
