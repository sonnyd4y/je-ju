# 제주 동네가게 AI Agent

제주 AI·빅데이터 활용 AI Agent 개발 챌린지 출품작. 계획은 [개발계획.md](개발계획.md), 진행 기록은 [개발진행.md](개발진행.md).

공공 인허가·유동인구·카드·외식업·리뷰 데이터를 도구로 조회하는 **단일 AI Agent**입니다.

- **도민 사장님**: 우리 가게 확인, 언제·어떤 손님이 오는지, 리뷰 분석 → 홍보 문구 초안 → 사장님 승인 후 확정
- **관광객**: 덜 붐비는 시간·지역의 현지 식당 추천 (도민 생활권 과밀 지역은 덜 추천)

## Agent 구조

```
사용자 (사장님 / 관광객) ── 글 + 사진
        │
        ▼
  Agent 루프 (app/agent/loop.py, Claude 도구 호출)
   판단 → 도구 선택 → 실행 → 결과 확인 → 다시 판단 … → 근거와 함께 답
        │
        ├─ find_store / search_stores      가게 찾기·목록       (780 인허가)
        ├─ area_insight                    상권 요약            (583, 490, 502, 495, 1048, 780)
        ├─ predict_crowd                   혼잡 예측 (583, 490, 502 + 수요 예측 모델)
        ├─ recommend_stores                관광객 추천 의사결정 모델 (다기준 가중 점수)
        ├─ resident_balance                도민 생활권 과밀도    (583)
        ├─ check_naver_listed              네이버 지도 등록 여부  (780 + 네이버 지역 검색)
        ├─ analyze_reviews                 리뷰 요인 분석        (903)
        ├─ marketing_brief                 마케팅 브리프 (진단·타깃·시점·메시지, 근거 번호 E1…)
        ├─ save_draft / decide_draft / list_drafts   초안(문장마다 근거) → 사람 승인 → 확정, 변경 이력
        ├─ generate_background             생성형 배경 (Gemini 나노바나나, 글자·음식·사람 없음)
        └─ render_card                     메뉴판·피드·스토리 카드 PNG (템플릿, 글자·가격 정확)
```

| Agent가 스스로 함 | 사람 승인 필요 |
|---|---|
| 데이터 조회·분석, 후보 추천, 리뷰 분류, 초안 작성 | 메뉴 가격, 홍보 문구·안내문 확정 |

승인 단계는 프롬프트뿐 아니라 **코드로 강제**합니다. 초안을 만든 같은 차례에서는 확정할 수 없고, 사용자가 답한 다음 차례에서만 `decide_draft`가 동작합니다 ([app/tools/drafts.py](app/tools/drafts.py)).

## 폴더

```
app/
  agent/    loop.py(Agent 루프) · tools.py(도구 정의·입력 검증) · prompts.py(시스템 프롬프트)
  tools/    stores.py · insight.py · reviews.py · drafts.py
  data/     db.py(SQLite) · regions.py(법정동↔행정동 대응표)
  api/      main.py (FastAPI, SSE 스트리밍)
data/       raw(허브 원본, git 제외) · processed(jeju.db) · sample · meta
scripts/    수집·전처리 · chat.py(터미널 대화) · eval_agent.py(시나리오 평가)
tests/      pytest (API 키 없이 실행)
```

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env                    # ANTHROPIC_API_KEY 입력

# 데이터 준비 (허브에서 받은 CSV를 data/raw/<ID>/ 에 넣은 뒤)
python scripts/check_data.py            # 빠진 데이터 확인
python scripts/fetch_hub_api.py         # API형 데이터 수집 (583, 591, 592, 811, 837)
python scripts/build_store_db.py        # 음식점 인허가 → jeju.db
python scripts/build_insight_db.py      # 분석용 테이블 → jeju.db
python scripts/check_naver.py 애월       # 지역 가게의 네이버 등록 여부 확인 (네이버 키 필요)

python scripts/train_demand.py          # 방문 수요 예측 모델 학습·검증 → data/processed/demand_model.joblib

# Agent
uvicorn app.api.main:app --port 8000    # 웹 화면: 브라우저에서 http://localhost:8000
python scripts/chat.py --mode owner     # 터미널 대화 (사장님)
python scripts/chat.py --mode tourist   # 터미널 대화 (관광객)

# 검증
python -m pytest -q                     # 단위 테스트 (키 불필요)
python scripts/eval_agent.py            # 시나리오 평가 (API 비용 발생) → docs/eval_results.json
python scripts/eval_agent.py --model claude-haiku-5-5   # 모델별 품질·비용 비교
```

## 데이터 처리 요약

| 항목 | 처리 |
|---|---|
| 지역 연결 | 가게 주소는 법정동, 유동인구는 행정동 → [regions.py](app/data/regions.py) 대응표로 연결 (영업 중 20,954곳 전부 연결) |
| 유동인구(583) | 하루 누적 집계값이라 사람 수가 아닌 구성비·비율로만 사용 |
| 식당 시간대 | 2019년(코로나 이전) 외식업 POS 비율에 최근 12개월 카드 데이터로 보정 (결정 D-01) |
| 혼잡 예측 | 요일 계수 × 시간대 비율 × 관광 밀도 → 제주 전체 분포 기준 한산/보통/붐빔. 실시간 아님 |
| 리뷰(903) | 작성자 이름·등급·사진 URL 삭제. 규칙 기반 요인 분류 (재현 가능) |
| 와이파이(568) | 장소명의 AP 번호 제거 후 장소 단위 합산, 숫자 오타("1012`") 정리 |

## 의사결정 모델

| 모델 | 방법 | 검증 |
|---|---|---|
| 방문 수요 예측 | scikit-learn HistGradientBoosting (요일·공휴일·연휴·계절·동네) | 2026-03~04 검증: 오차 18.9% (요일 평균 22.8%), 혼잡 등급 일치 59.4% (36.9%). 공휴일은 일요일 패턴으로 대체 |
| 관광객 추천 | 다기준 가중 점수: 덜 붐빔·생활권 여유·숨은 가게·오래된 가게 | 같은 입력 → 같은 순위, 기준별 점수 공개 |

## 사용 모델·외부 의존성

- Google Gemini 이미지 모델 `gemini-nano-banana-2.1` (카드 배경만 생성, SynthID 워터마크, 하루 30장 한도)
- 네이버 API HUB 지역 검색 (네이버 지도 등록 여부·좌표, 하루 25,000회 한도)
- Claude API (`claude-opus-5-5`, 추론 강도 medium, `.env`로 변경 가능). 안전 분류기 거절 시 서버 측 자동 대체 모델 사용
- 인터넷 연결 필요 (Claude API). 데이터 조회는 로컬 SQLite
- API 키·개인정보는 저장소에 포함하지 않음 (`.env`는 git 제외)
