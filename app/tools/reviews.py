"""리뷰 분석 도구: analyze_reviews (원본: 903 구글 음식점 리뷰, 작성자 정보 삭제본).

규칙 기반 요인 분류 (같은 입력이면 항상 같은 결과):
  1. 리뷰를 절(문장·'지만'·'는데' 단위)로 나눈다
  2. 절에 요인 단어(맛, 양, 가격, 친절, 위생, 주차, 대기, 분위기)가 있으면
     부정 표현 → 부정, 긍정 표현 → 긍정, 둘 다 없으면 별점(4점 이상 긍정, 2점 이하 부정)
  3. 요인별 긍정·부정 수와 대표 문장을 돌려준다
"""
import re
from collections import Counter, defaultdict

from rapidfuzz import fuzz, process

from app.data import db

FACTORS = {
    "맛": ["맛", "육즙", "양념", "국물", "간이", "짜", "짭", "싱겁", "냄새", "신선", "싱싱", "식감", "느끼", "조미료"],
    "양": ["양이", "양은", "양도", "양 ", "푸짐", "넉넉", "배불"],
    "가격": ["가격", "가성비", "비싸", "저렴", "비쌈", "값", "만원"],
    "친절": ["친절", "서비스", "직원", "사장님", "응대", "알바", "주인"],
    "위생": ["깨끗", "청결", "위생", "더럽", "지저분", "파리", "머리카락", "벌레"],
    "주차": ["주차"],
    "대기": ["대기", "웨이팅", "기다", "줄을", "줄이", "오래 걸", "늦게 나"],
    "분위기": ["바다뷰", "오션뷰", "뷰가", "뷰도", "뷰는", "인테리어", "분위기", "시끄", "쾌적", "넓", "좁", "매장", "자리"],
}
NEG = [
    "맛없", "별로", "아쉽", "아쉬", "불친절", "비싸", "비쌈", "짜고", "짜요", "짜다", "짭", "냄새", "최악", "그닥", "그다지",
    "비추", "더럽", "지저분", "파리", "벌레", "시끄", "좁", "불편", "실망", "이상", "못 먹", "못먹", "아까", "없었", "없어요",
    "없음", "없고", "느끼", "오래 걸", "기다려야", "부족", "적어", "적고", "평범", "무난", "글쎄", "애매", "두드러기", "떨어", "쏘쏘", "그냥 그",
]
POS = [
    "맛있", "맛나", "맛집", "좋", "친절", "푸짐", "깨끗", "깔끔", "넓", "최고", "추천", "훌륭", "저렴", "가성비", "싱싱",
    "신선", "쾌적", "만족", "감사", "넉넉", "편해", "편하", "빠르", "정갈", "또 올", "재방문", "단골", "탱글", "바삭",
]
# 부정 단어를 다시 부정하는 표현 ("짜지 않고", "비싸지 않")은 긍정 쪽으로 본다
NEG_NEGATED = re.compile(r"(짜|비싸|느끼|좁|시끄|불편)지\s?않|냄새\S*\s?(안\s?|없)")  # '냄새밸일이 없어요'도 긍정
SPLIT = re.compile(r"[.!?~\n…]+|지만|는데|은데|던데|으나|ㅠ+|ㅜ+")


def _clauses(text: str) -> list[str]:
    text = (text or "").replace("리뷰", "후기")  # '리뷰가'의 '뷰가'가 분위기(뷰)로 잡히지 않도록
    return [c.strip() for c in SPLIT.split(text) if len(c.strip()) >= 2]


def _polarity(clause: str, stars: float | None) -> int:
    c = NEG_NEGATED.sub("좋", clause)
    if any(w in c for w in NEG):
        return -1
    if any(w in c for w in POS):
        return 1
    if stars is not None:
        return 1 if stars >= 4 else -1 if stars <= 2 else 0
    return 0


def classify(text: str, stars: float | None = None) -> dict[str, int]:
    """리뷰 한 건 → {요인: +1/-1}. 같은 요인이 여러 번 나오면 마지막 절 기준이 아니라 합산 부호."""
    score: dict[str, int] = defaultdict(int)
    for c in _clauses(text):
        for f, words in FACTORS.items():
            if any(w in c for w in words):
                score[f] += _polarity(c, stars)
    return {f: (1 if v > 0 else -1) for f, v in score.items() if v != 0}


def _quote(text: str, n=70) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _model_aspects(store: str) -> list[dict]:
    """scripts/build_review_sentiment.py가 만든 모델 판단 결과 (없으면 빈 목록 → 규칙 사용)."""
    try:
        return db.rows("SELECT review_id, factor, polarity, clause FROM review_aspects WHERE store = ?", [store])
    except Exception:
        return []


def analyze_reviews(store_name: str, limit_quotes: int = 2) -> dict:
    """가게 리뷰를 요인별 긍정·부정으로 나누고 대표 문장을 뽑는다."""
    names = [r["store"] for r in db.rows("SELECT DISTINCT store FROM reviews")]
    hit = process.extractOne(store_name, names, scorer=fuzz.WRatio)
    if not hit or hit[1] < 70:
        return {
            "error": f"'{store_name}' 리뷰 데이터가 없음",
            "available_stores": names,
            "note": "현재 리뷰 데이터는 2021년 구글 리뷰 10개 식당분(검증용)만 있음",
        }
    store = hit[0]
    rows = db.rows("SELECT stars, contents FROM reviews WHERE store = ?", [store])
    texts = [r for r in rows if r["contents"]]

    pos, neg = Counter(), Counter()
    quotes: dict[tuple[str, int], list[tuple[int, str]]] = defaultdict(list)
    aspects = _model_aspects(store)
    if aspects:
        # 오픈소스 감성 모델(KoELECTRA) 판단 사용: 리뷰·요인별로 절 판단을 합산
        by_review: dict[tuple[int, str], int] = defaultdict(int)
        clause_of: dict[tuple[int, str, int], str] = {}
        for a in aspects:
            by_review[(a["review_id"], a["factor"])] += a["polarity"]
            clause_of.setdefault((a["review_id"], a["factor"], a["polarity"]), a["clause"])
        for (rid, f), v in by_review.items():
            if v == 0:
                continue
            p = 1 if v > 0 else -1
            (pos if p > 0 else neg)[f] += 1
            clause = clause_of.get((rid, f, p), "")
            quotes[(f, p)].append((abs(len(clause) - 30), _quote(clause)))
    else:
        for r in texts:
            for f, p in classify(r["contents"], r["stars"]).items():
                (pos if p > 0 else neg)[f] += 1
                # 대표 문장: 그 요인이 들어간 절, 너무 짧거나 긴 것은 뒤로
                clause = next((c for c in _clauses(r["contents"]) if any(w in c for w in FACTORS[f])), r["contents"])
                quotes[(f, p)].append((abs(len(clause) - 30), _quote(clause)))

    def top(counter, sign):
        out = []
        for f, n in counter.most_common():
            qs = [q for _, q in sorted(quotes[(f, sign)])[:limit_quotes]]
            out.append({"factor": f, "count": n, "share_of_text_reviews": f"{n / len(texts):.0%}", "examples": qs})
        return out

    stars = [r["stars"] for r in rows if r["stars"] is not None]
    dist = Counter(int(s) for s in stars)
    return {
        "store": store,
        "reviews": len(rows),
        "with_text": len(texts),
        "avg_stars": round(sum(stars) / len(stars), 2) if stars else None,
        "stars_distribution": {f"{k}점": dist.get(k, 0) for k in range(5, 0, -1)},
        "strengths": top(pos, 1)[:4],
        "complaints": top(neg, -1)[:4],
        "method": ("요인은 규칙(요인 단어)으로 찾고, 긍정/부정은 오픈소스 한국어 감성 모델(KoELECTRA, Copycats/koelectra-base-v3-"
                   "generalized-sentiment-analysis)로 판단. 확신이 낮으면 별점으로 보완." if aspects else
                   "규칙 기반 요인 분류 (요인 단어 + 긍정/부정 표현, 애매하면 별점).") + " 작성자 정보는 저장·출력하지 않음.",
        "notes": ["2021년 구글 리뷰(검증용 데이터)이며 현재 가게 상황과 다를 수 있음"],
        "sources": db.cite("reviews"),
    }
