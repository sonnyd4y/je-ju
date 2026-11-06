# 제주 동네가게 AI Agent

제주 AI·빅데이터 활용 AI Agent 개발 챌린지 출품작. 계획은 [개발계획.md](개발계획.md) 참고.

## 폴더 구조

```
app/        agent(루프·프롬프트) / tools(도구) / data(로더) / templates(카드 HTML) / ui(Streamlit)
data/
  manifest.csv   받아야 할 허브 데이터 목록 (ID, 우선순위, 상세페이지, 저장위치)
  raw/<ID>/      허브에서 받은 원본 CSV를 ID별 폴더에 그대로 넣기 (git 제외)
  sample/        스키마 확인용 미리보기 CSV
  processed/     전처리 결과 (jeju.db)
  meta/          허브·센터 전체 데이터 목록 원본 JSON
scripts/    수집·전처리 스크립트
docs/       기획서, 데이터 명세, 매뉴얼
```

## 시작하기

```bash
pip install -r requirements.txt
cp .env.example .env           # API 키 입력
python scripts/check_data.py   # 어떤 데이터가 아직 없는지 확인
python scripts/build_store_db.py   # 음식점 인허가 → data/processed/jeju.db
```

## 데이터 받는 법

1. [제주데이터허브](https://jejudatahub.net) 회원가입 후 로그인
2. `data/manifest.csv`의 상세페이지에서 이용 신청 (P1부터)
3. 승인 후 내려받은 CSV를 `data/raw/<ID>/`에 넣기
4. `python scripts/check_data.py`로 확인
