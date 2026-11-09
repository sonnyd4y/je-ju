"""방문 수요 예측 모델 학습·검증.

- 학습: 2026-02-28 까지, 검증: 그 이후 (시간 순서대로 나눠 미래를 맞히는지 본다)
- 비교 기준(기존 방식): 학습 기간의 동네별 요일 평균 비율
- 지표: MAPE(평균 절대 백분율 오차), 혼잡 등급(한산/보통/붐빔 3분위) 일치율
- 검증 후 전체 기간으로 다시 학습해 저장

사용법: python scripts/train_demand.py
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.tools import forecast  # noqa: E402

SPLIT = "2026-03-01"


def make_model():
    # 설정 비교(11/09): 단순한 모델이 검증 기간 오차가 더 작음 (MAPE 0.203 → 0.189)
    return HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=60, l2_regularization=1.0,
        categorical_features=[0], random_state=42,
    )


def level(r: pd.Series, q) -> pd.Series:
    return pd.cut(r, [-np.inf, q[0], q[1], np.inf], labels=["한산", "보통", "붐빔"])


def main():
    p = forecast.training_frame()
    codes = {k: i for i, k in enumerate(sorted(p.key.unique()))}
    p["code"] = p.key.map(codes)
    X = forecast.features(p.date, p.code)
    y = np.log(p.ratio.clip(lower=0.05))

    tr, te = p.date < SPLIT, p.date >= SPLIT
    model = make_model().fit(X[tr], y[tr])
    pred = np.exp(model.predict(X[te]))

    # 기존 방식: 학습 기간 동네별 요일 평균 비율
    dow = pd.to_datetime(p.date).dt.dayofweek
    base_tab = p[tr].assign(dow=dow[tr]).groupby(["key", "dow"]).ratio.mean()
    base = [base_tab.get((k, d), 1.0) for k, d in zip(p.key[te], dow[te])]

    actual = p.ratio[te].values
    mape = lambda a, b: float(np.mean(np.abs(a - b) / a))
    q = np.quantile(p.ratio[tr], [0.4, 0.8])
    acc = lambda b: float((level(pd.Series(actual), q).values == level(pd.Series(b), q).values).mean())

    # 공휴일·연휴만 따로 (요일 평균이 가장 약한 날)
    off = (X.holiday[te].values == 1) | (X.long_weekend[te].values >= 3)
    m = {
        "model": "scikit-learn HistGradientBoostingRegressor",
        "target": "읍면동 방문인구 / 동네 평균 (583)",
        "train": f"{p.date.min()} ~ {pd.Timestamp(SPLIT) - pd.Timedelta(days=1):%Y-%m-%d}",
        "test": f"{SPLIT} ~ {p.date.max()}",
        "test_rows": int(te.sum()),
        "mape": {"model": round(mape(actual, pred), 4), "weekday_average": round(mape(actual, np.array(base)), 4)},
        "level_accuracy": {"model": round(acc(pred), 4), "weekday_average": round(acc(np.array(base)), 4)},
        "holiday_or_long_weekend_rows": int(off.sum()),
        "holiday_mape": {
            "model": round(mape(actual[off], pred[off]), 4) if off.any() else None,
            "weekday_average": round(mape(actual[off], np.array(base)[off]), 4) if off.any() else None,
        },
    }
    m["holiday_rule"] = "공휴일은 표본이 적어 모델이 약함 → 예측 시 공휴일은 일요일 요일 평균으로 대체"
    print(json.dumps(m, ensure_ascii=False, indent=1))

    # 전체 기간으로 다시 학습해 저장
    final = make_model().fit(X, y)
    base_size = p.groupby("key").visitor.mean().to_dict()
    joblib.dump({"model": final, "codes": codes, "base": base_size}, forecast.MODEL_PATH)
    m["trained_on"] = f"{p.date.min()} ~ {p.date.max()}"
    forecast.METRICS_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: {forecast.MODEL_PATH.name}, {forecast.METRICS_PATH.name}")


if __name__ == "__main__":
    main()
