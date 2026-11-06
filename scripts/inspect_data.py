"""data/raw 의 CSV를 열어 인코딩, 행·열 수, 컬럼, 기간, 빈 값 비율을 점검한다.

사용법: python scripts/inspect_data.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
DATE_HINTS = ("base_year_month", "기준", "년월", "일자", "날짜", "date", "Date", "YearMonth", "연월", "월")


def read(path):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str, low_memory=False), enc
        except UnicodeDecodeError:
            continue
    return None, "인코딩 실패"


def main():
    for p in sorted((ROOT / "data/raw").glob("*/*.csv")):
        if p.parent.name == "903":
            continue
        df, enc = read(p)
        rel = p.relative_to(ROOT).as_posix()
        if df is None:
            print(f"!! {rel}: {enc}")
            continue
        print(f"== {rel}  [{enc}] {len(df):,}행 x {df.shape[1]}열")
        print("   컬럼:", list(df.columns)[:16])
        for c in df.columns:
            if any(h in c for h in DATE_HINTS) and df[c].notna().any():
                v = df[c].dropna().astype(str)
                print(f"   기간({c}): {v.min()} ~ {v.max()}")
                break
        empty = df.isna().mean()
        bad = empty[empty > 0.5]
        if len(bad):
            print("   빈 값 50% 이상:", {k: f"{v:.0%}" for k, v in bad.items()})
        if df.duplicated().sum():
            print(f"   완전 중복 행: {df.duplicated().sum():,}")

    rv = list((ROOT / "data/raw/903").glob("*.csv"))
    if rv:
        d = pd.concat([pd.read_csv(f, dtype=str) for f in rv])
        print(f"== data/raw/903 (리뷰 {len(rv)}개 파일) {len(d):,}행, 컬럼 {list(d.columns)}")


if __name__ == "__main__":
    main()
