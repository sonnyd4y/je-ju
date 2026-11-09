"""리뷰 감성 분석 (오픈소스 모델) → jeju.db review_aspects 테이블.

모델: Copycats/koelectra-base-v3-generalized-sentiment-analysis (Hugging Face, Apache-2.0, KoELECTRA 기반, 약 1.1억 파라미터)
     라벨 0 = 부정, 1 = 긍정. CPU에서 실행 (GPU 불필요)

처리
  1. 리뷰를 절로 나누고 (app/tools/reviews.py와 같은 규칙), 요인 단어(맛·양·가격·친절·위생·주차·대기·분위기)가 있는 절만 고른다
  2. 그 절의 긍정/부정을 모델로 판단하고, 규칙 판단도 함께 저장해 일치율을 기록한다
  3. analyze_reviews는 이 테이블이 있으면 모델 판단을 쓴다 (서버에는 PyTorch가 필요 없음)

사용법: python scripts/build_review_sentiment.py   (처음 실행 시 모델 내려받기 약 450MB)
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.data import db  # noqa: E402
from app.tools import reviews  # noqa: E402

MODEL_ID = "Copycats/koelectra-base-v3-generalized-sentiment-analysis"
MIN_CONFIDENCE = 0.6  # 이보다 확신이 낮으면 별점으로 보완


def main():
    from transformers import pipeline

    rows = db.rows("SELECT review_id, store, stars, contents FROM reviews WHERE length(contents) > 0")
    items = []
    for r in rows:
        for c in reviews._clauses(r["contents"]):
            factors = [f for f, words in reviews.FACTORS.items() if any(w in c for w in words)]
            if factors:
                items.append((r["review_id"], r["store"], r["stars"], c, factors))
    print(f"리뷰 {len(rows)}건 → 요인이 있는 절 {len(items)}개")

    t = time.time()
    clf = pipeline("text-classification", model=MODEL_ID, device=-1)
    preds = clf([c for _, _, _, c, _ in items], batch_size=32, truncation=True, max_length=128)
    print(f"모델 판단 {len(items)}개, {time.time() - t:.0f}초")

    out, agree, total = [], 0, 0
    for (rid, store, stars, clause, factors), p in zip(items, preds):
        label = 1 if str(p["label"]) in ("1", "LABEL_1", "positive") else -1
        score = float(p["score"])
        if score < MIN_CONFIDENCE and stars is not None:  # 애매하면 별점으로
            label = 1 if stars >= 4 else -1 if stars <= 2 else label
        rule = reviews._polarity(clause, stars)
        for f in factors:
            out.append((rid, store, clause, f, label, round(score, 3), rule))
            if rule != 0:
                total += 1
                agree += int(rule == label)

    with sqlite3.connect(db.DB_PATH) as con:
        con.execute("DROP TABLE IF EXISTS review_aspects")
        con.execute("CREATE TABLE review_aspects (review_id INTEGER, store TEXT, clause TEXT, factor TEXT, "
                    "polarity INTEGER, confidence REAL, rule_polarity INTEGER)")
        con.executemany("INSERT INTO review_aspects VALUES (?,?,?,?,?,?,?)", out)
        con.execute("CREATE INDEX ix_aspects_store ON review_aspects(store)")
    meta = {"model": MODEL_ID, "clauses": len(items), "aspect_rows": len(out),
            "rule_model_agreement": round(agree / max(total, 1), 3), "min_confidence": MIN_CONFIDENCE}
    (ROOT / "data/processed/review_sentiment_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
