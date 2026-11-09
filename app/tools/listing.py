"""네이버 지도(스마트플레이스) 등록 자료 묶음: make_listing_kit.

인허가 데이터(780)로 미리 채울 수 있는 항목을 채우고, 사장님이 준비할 것을 목록으로 준다.
소개글은 Agent가 사장님 말씀·리뷰 근거로 save_draft(kind='intro')로 만든다.
"""
from app.data import db
from app.tools import naver

# 인허가 업태 → 네이버 업종 예시 (등록 화면에서 고를 때 참고)
CATEGORY_HINT = {
    "한식": "한식", "식육(숯불구이)": "육류,고기요리", "횟집": "생선회", "중국식": "중식", "일식": "일식당",
    "경양식": "양식", "분식": "분식", "커피숍": "카페", "까페": "카페", "호프/통닭": "호프,요리주점",
    "통닭(치킨)": "치킨,닭강정", "정종/대포집/소주방": "요리주점", "패스트푸드": "패스트푸드", "김밥(도시락)": "김밥",
}


def make_listing_kit(store_id: int) -> dict:
    """네이버 스마트플레이스 등록에 필요한 자료: 인허가로 채운 기본 정보 + 준비물 + 순서."""
    rows = db.rows("SELECT * FROM stores WHERE store_id=?", [store_id])
    if not rows:
        return {"error": f"store_id {store_id} 없음. find_store로 먼저 찾을 것."}
    s = rows[0]
    nv = naver.check_naver_listed(store_id)
    return {
        "store_id": store_id,
        "naver_status": nv.get("naver_status", "미확인"),
        "prefilled": {
            "업체명": s["name"],
            "업종 (네이버에서 고를 때 참고)": CATEGORY_HINT.get(s["category"] or "", s["category"] or "음식점"),
            "도로명 주소": s["addr_road"],
            "지번 주소": s["addr_jibun"],
            "영업 상태 (인허가 기준)": s["status"],
            "인허가일": s["open_date"],
        },
        "owner_prepares": [
            "사업자등록증 (등록 화면에서 확인용으로 올림)",
            "가게 사진 3장 이상: 간판·외관, 내부, 대표 메뉴",
            "대표 메뉴와 가격 (메뉴판 사진이 있으면 메뉴판 초안으로 정리 가능)",
            "영업시간·쉬는 날, 연락받을 전화번호",
            "소개글 (사장님 말씀을 바탕으로 초안 작성 가능)",
        ],
        "steps": [
            "네이버 스마트플레이스(smartplace.naver.com)에 네이버 아이디로 로그인",
            "'업체 신규 등록'에서 업체명·주소로 검색 → 없으면 새로 등록",
            "위 기본 정보와 사진·메뉴·영업시간·소개글 입력",
            "사업자등록증 확인 후 네이버 검수가 끝나면 지도에 노출",
        ],
        "note": "등록 화면 구성은 네이버 정책에 따라 바뀔 수 있음. 실제 등록은 사장님 본인 계정으로 진행",
        "sources": db.cite("stores") + ["네이버 지역 검색 (등록 여부)"],
    }
