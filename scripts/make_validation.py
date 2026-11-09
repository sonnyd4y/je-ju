"""정확도 검증용 시트 만들기 / 채점.

1) 만들기: python scripts/make_validation.py make
   docs/검증/네이버판별_표본50.xlsx  - 애월 판별 결과 표본(미등록 후보 25, 등록 15, 확인 필요 10). 링크를 눌러 네이버 지도에서 확인 후
                                      '실제' 칸에 등록 / 미등록 입력
   docs/검증/리뷰분류_표본100.xlsx   - 리뷰 100건과 규칙 분류 결과. '맞음' 칸에 O / X, 틀리면 '정답' 칸에 바른 분류(예: 맛+ 가격-)
2) 채점: python scripts/make_validation.py score  → docs/검증/검증결과.json
표본은 고정 시드(42)로 뽑아 재현 가능.
"""
import json
import sys
import urllib.parse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.data import db  # noqa: E402
from app.tools.reviews import classify  # noqa: E402

OUT = ROOT / "docs/검증"
NAVER = OUT / "네이버판별_표본50.xlsx"
REVIEW = OUT / "리뷰분류_표본100.xlsx"
STATUS = {0: "미등록 후보", 1: "등록", 2: "확인 필요"}


def _write(df: pd.DataFrame, path: Path, link_col: str | None, widths: dict):
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="검증")
        ws = w.sheets["검증"]
        for col, width in widths.items():
            ws.column_dimensions[col].width = width
        if link_col:
            idx = list(df.columns).index(link_col) + 1
            for r in range(2, len(df) + 2):
                c = ws.cell(row=r, column=idx)
                c.hyperlink, c.style = c.value, "Hyperlink"


def make():
    OUT.mkdir(parents=True, exist_ok=True)
    nc = db.query(
        "SELECT n.store_id, s.name, s.addr_road, s.addr_jibun, n.status, n.naver_title, n.naver_road "
        "FROM naver_check n JOIN stores s USING(store_id) WHERE s.emd='애월읍'"
    )
    parts = [nc[nc.status == st].sample(min(k, (nc.status == st).sum()), random_state=42)
             for st, k in ((0, 25), (1, 15), (2, 10))]
    s = pd.concat(parts).sample(frac=1, random_state=42)
    s["판별"] = s.status.map(STATUS)
    s["주소"] = s.addr_road.fillna(s.addr_jibun).str.replace("제주특별자치도 ", "")
    s["네이버 지도에서 찾기"] = "https://map.naver.com/p/search/" + (s.name + " 애월").map(urllib.parse.quote)
    s["실제(등록/미등록)"] = ""
    s["메모"] = ""
    s = s[["store_id", "name", "주소", "판별", "naver_title", "네이버 지도에서 찾기", "실제(등록/미등록)", "메모"]]
    s.columns = ["store_id", "가게 이름(인허가)", "주소", "판별", "네이버에서 찾은 이름", "네이버 지도에서 찾기", "실제(등록/미등록)", "메모"]
    _write(s, NAVER, "네이버 지도에서 찾기", {"B": 24, "C": 40, "D": 12, "E": 26, "F": 30, "G": 16, "H": 20})

    rv = db.query("SELECT review_id, store, stars, contents FROM reviews WHERE length(contents) >= 15")
    r = rv.sample(100, random_state=42).copy()
    r["규칙 분류"] = [
        " ".join(f"{k}{'+' if v > 0 else '-'}" for k, v in classify(t, st).items()) or "(해당 없음)"
        for t, st in zip(r.contents, r.stars)
    ]
    r["맞음(O/X)"] = ""
    r["정답(틀렸을 때)"] = ""
    r = r[["review_id", "store", "stars", "contents", "규칙 분류", "맞음(O/X)", "정답(틀렸을 때)"]]
    r.columns = ["review_id", "가게", "별점", "리뷰", "규칙 분류", "맞음(O/X)", "정답(틀렸을 때)"]
    _write(r, REVIEW, None, {"B": 16, "C": 6, "D": 70, "E": 20, "F": 10, "G": 20})
    print(f"저장: {NAVER.relative_to(ROOT)} ({len(s)}건), {REVIEW.relative_to(ROOT)} ({len(r)}건)")


def score():
    res = {}
    if NAVER.exists():
        n = pd.read_excel(NAVER).dropna(subset=["실제(등록/미등록)"])
        n["실제"] = n["실제(등록/미등록)"].str.strip()
        judged = n[n["판별"] != "확인 필요"]
        correct = ((judged["판별"] == "등록") & (judged["실제"] == "등록")) | (
            (judged["판별"] == "미등록 후보") & (judged["실제"] == "미등록"))
        unl = judged[judged["판별"] == "미등록 후보"]
        res["naver"] = {
            "checked": int(len(n)),
            "accuracy_excluding_review_needed": round(float(correct.mean()), 3) if len(judged) else None,
            "unlisted_precision": round(float((unl["실제"] == "미등록").mean()), 3) if len(unl) else None,
            "review_needed_actually_listed": round(float((n[n["판별"] == "확인 필요"]["실제"] == "등록").mean()), 3)
            if (n["판별"] == "확인 필요").any() else None,
        }
    if REVIEW.exists():
        r = pd.read_excel(REVIEW).dropna(subset=["맞음(O/X)"])
        ok = r["맞음(O/X)"].astype(str).str.strip().str.upper().isin(["O", "0", "ㅇ", "맞음"])
        res["reviews"] = {"checked": int(len(r)), "accuracy": round(float(ok.mean()), 3) if len(r) else None}
    (OUT / "검증결과.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"make": make, "score": score}[sys.argv[1] if len(sys.argv) > 1 else "make"]()
