"""제주 지역명 처리.

가게 주소(780)는 법정동(예: 이도이동, 서귀동), 유동인구(583)는 행정동(예: 이도2동, 중앙동) 기준이다.
읍·면은 둘이 같고, 동 지역만 아래 대응표로 연결한다.

- 하나의 법정동이 여러 행정동에 걸치는 경우(서귀동, 삼도일동 등)는 관련 행정동을 모두 묶어서 본다.
- 대응표는 제주특별자치도 행정구역 현황 기준으로 정리했다. 일부 경계 지역은 근사값이다.
"""
import re

# (시, 행정동) → 그 행정동에 속한 법정동
ADMIN_TO_LEGAL = {
    ("제주시", "일도1동"): ["일도일동"],
    ("제주시", "일도2동"): ["일도이동"],
    ("제주시", "이도1동"): ["이도일동"],
    ("제주시", "이도2동"): ["이도이동", "도남동"],
    ("제주시", "삼도1동"): ["삼도일동"],
    ("제주시", "삼도2동"): ["삼도이동", "삼도일동"],
    ("제주시", "용담1동"): ["용담일동"],
    ("제주시", "용담2동"): ["용담이동", "용담삼동"],
    ("제주시", "건입동"): ["건입동"],
    ("제주시", "화북동"): ["화북일동", "화북이동"],
    ("제주시", "삼양동"): ["삼양일동", "삼양이동", "삼양삼동", "도련일동", "도련이동"],
    ("제주시", "봉개동"): ["봉개동", "회천동", "용강동"],
    ("제주시", "아라동"): ["아라일동", "아라이동", "오등동", "영평동", "월평동"],
    ("제주시", "오라동"): ["오라일동", "오라이동", "오라삼동"],
    ("제주시", "연동"): ["연동"],
    ("제주시", "노형동"): ["노형동", "해안동"],
    ("제주시", "외도동"): ["외도일동", "외도이동", "내도동", "도평동"],
    ("제주시", "이호동"): ["이호일동", "이호이동"],
    ("제주시", "도두동"): ["도두일동", "도두이동"],
    ("서귀포시", "송산동"): ["서귀동", "보목동"],
    ("서귀포시", "정방동"): ["서귀동"],
    ("서귀포시", "중앙동"): ["서귀동"],
    ("서귀포시", "천지동"): ["서귀동"],
    ("서귀포시", "효돈동"): ["하효동", "신효동"],
    ("서귀포시", "영천동"): ["상효동", "토평동"],
    ("서귀포시", "동홍동"): ["동홍동"],
    ("서귀포시", "서홍동"): ["서홍동"],
    ("서귀포시", "대륜동"): ["법환동", "서호동", "호근동"],
    ("서귀포시", "대천동"): ["강정동", "도순동", "영남동", "월평동"],
    ("서귀포시", "중문동"): ["중문동", "대포동", "하원동", "회수동"],
    ("서귀포시", "예래동"): ["상예동", "하예동", "색달동"],
}

EUP_MYEON = {
    "제주시": ["한림읍", "애월읍", "구좌읍", "조천읍", "한경면", "추자면", "우도면"],
    "서귀포시": ["대정읍", "남원읍", "성산읍", "안덕면", "표선면"],
}
for _city, _names in EUP_MYEON.items():
    for _n in _names:
        ADMIN_TO_LEGAL[(_city, _n)] = [_n]

LEGAL_TO_ADMIN: dict[tuple[str, str], list[str]] = {}
for (_city, _admin), _legals in ADMIN_TO_LEGAL.items():
    for _l in _legals:
        LEGAL_TO_ADMIN.setdefault((_city, _l), []).append(_admin)


def _norm(s: str) -> str:
    s = re.sub(r"\s+", "", s or "")
    s = s.replace("제주특별자치도", "").replace("제주도", "")
    return s


def resolve(name: str) -> dict | None:
    """사용자가 말한 지역명을 가게 조회용 법정동 목록과 유동인구 조회용 행정동 목록으로 바꾼다.

    '애월', '애월읍', '이도2동', '이도이동', '서귀동', '서귀포시 중문' 같은 입력을 모두 받는다.
    시 이름만 오면 그 시 전체.
    """
    q = _norm(name)
    city = None
    for c in ("서귀포시", "제주시"):
        if q.startswith(c):
            city, q = c, q[len(c):]
            break
    if not q and city:
        admins = [a for (c, a) in ADMIN_TO_LEGAL if c == city]
        legals = sorted({l for (c, a), ls in ADMIN_TO_LEGAL.items() if c == city for l in ls})
        return {"label": city, "city": city, "admin": admins, "legal": legals}
    if q in ("서귀포", "제주"):
        return resolve(q + "시")

    def match(names):
        exact = [k for k in names if k[1] == q and (city is None or k[0] == city)]
        if exact:
            return exact
        # '애월' → '애월읍', '중문' → '중문동', '이도2' → '이도2동'
        return [k for k in names if re.fullmatch(re.escape(q) + r"(읍|면|동)", k[1]) and (city is None or k[0] == city)]

    hits = match(ADMIN_TO_LEGAL.keys())
    hits = [k for k in hits if k[0] == hits[0][0]]  # 같은 이름이 두 시에 있으면 첫 번째 시로 한정
    if hits:
        admins = [a for _, a in hits]
        legals = sorted({l for k in hits for l in ADMIN_TO_LEGAL[k]})
        return {"label": hits[0][1], "city": hits[0][0], "admin": admins, "legal": legals}
    hits = match(LEGAL_TO_ADMIN.keys())
    hits = [k for k in hits if k[0] == hits[0][0]]
    if hits:
        admins = sorted({a for k in hits for a in LEGAL_TO_ADMIN[k]})
        legals = sorted({l for _, l in hits})
        return {"label": hits[0][1], "city": hits[0][0], "admin": admins, "legal": legals}
    return None


def admin_of(city: str | None, legal: str | None) -> list[str]:
    """가게 주소의 법정동 → 행정동 목록."""
    return LEGAL_TO_ADMIN.get((city, legal), [])
