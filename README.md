# 제주 동네가게 AI Agent

제주 AI·빅데이터 활용 AI Agent 개발 챌린지 출품작입니다.
제주 공공데이터(음식점 인허가·유동인구·카드·외식업·리뷰·관광지)를 **도구(Tool)로 조회하고 판단하는 AI Agent**가 두 사용자를 돕습니다.

| 사용자 | Agent가 하는 일 |
|---|---|
| **도민 가게 사장님** | 우리 동네 손님 분석 → 네이버 지도 등록 확인·등록 자료 → 근거 있는 홍보 문구·메뉴판·홍보 이미지 초안 → **사장님 승인 후 확정** |
| **관광객** | 덜 붐비는 시간·동네의 현지 식당 추천 (도민 생활권이 붐비는 동네는 덜 추천), 하루 일정, 지도 |

- 데모: **https://jeju-local-agent.web.app** (화면: Firebase Hosting · 서버: Google Cloud Run `https://je-ju-426798142372.asia-northeast3.run.app`)
- 소스: https://github.com/sonnyd4y/je-ju
- 문서: [사용자 매뉴얼](docs/사용자매뉴얼.md) · [데이터 활용 명세](docs/데이터활용명세.md) · [개발 진행 기록·결정 사항](개발진행.md) · [개발 계획](개발계획.md)

---

## 1. Agent 구성

```
사용자 (사장님 / 관광객) ── 글 · 사진 · 음성
        │
        ▼
  Agent 루프 (app/agent/loop.py) ─ Claude 도구 호출, 스트리밍
   판단 → 도구 선택 → 실행 → 결과 확인 → 다시 판단 … → 근거와 함께 답
        │
        ├─ 조회·분석     find_store · search_stores · area_insight · resident_balance · place_crowd
        ├─ 의사결정 모델  predict_crowd (수요 예측) · recommend_stores (다기준 추천) · plan_itinerary (일정·길찾기)
        ├─ 네이버       check_naver_listed (등록 여부) · link_naver_name (간판·네이버 상호가 다를 때 주소로 연결) · make_listing_kit (등록 자료)
        ├─ 리뷰         analyze_reviews (구글 리뷰 903) · analyze_review_text (사장님이 붙여넣은 리뷰)
        ├─ 마케팅       marketing_brief (진단·타깃·시점·메시지, 근거 번호)
        ├─ 초안·승인     save_draft → decide_draft (사람 승인) · list_drafts (이력)
        └─ 이미지       render_card (메뉴판·피드·스토리 PNG) · generate_background (생성형 배경)
```

도구는 19개이며 정의와 입력 검증은 [app/agent/tools.py](app/agent/tools.py)에 있습니다.

### 자율 범위

| Agent가 스스로 함 | 사람 승인 필요 |
|---|---|
| 데이터 조회·분석, 혼잡 예측, 후보 추천, 리뷰 분류, 홍보 초안·이미지 미리보기 | 메뉴 가격, 홍보 문구·안내문 **확정** |

- 승인은 프롬프트만이 아니라 **코드로 강제**합니다. 초안을 만든 같은 차례에서는 `decide_draft`가 막히고, 사용자가 답한 다음 차례에서만 동작합니다 ([app/agent/tools.py](app/agent/tools.py), [app/tools/drafts.py](app/tools/drafts.py)).
- 홍보 문장은 문장마다 근거(데이터 근거, '사장님 말씀', '사진')가 있어야 저장됩니다. 근거 없는 최상급 표현('제주 최고' 등)은 거절합니다.

### 사용 모델

| 역할 | 모델 | 비고 |
|---|---|---|
| Agent 추론 (사장님) | Claude `claude-sonnet-5-5` | 홍보·승인 절차처럼 단계가 많은 일 |
| Agent 추론 (관광객) | Claude `claude-haiku-5-5` | 조회 중심이라 작은 모델로 비용 절감 |
| 방문 수요 예측 | scikit-learn HistGradientBoosting | 직접 학습 ([scripts/train_demand.py](scripts/train_demand.py)) |
| 리뷰 감성 | 오픈소스 KoELECTRA (Apache-2.0) | 미리 계산해 DB에 저장, 실행 중 GPU 불필요 |
| 관광객 추천 | 다기준 가중 점수 (덜 붐빔 .35 · 생활권 여유 .25 · 숨은 가게 .20 · 오래된 가게 .20) | 기준별 점수 공개 |
| 홍보 이미지 배경 | Google Gemini `gemini-nano-banana-2.1` | 배경만 생성 (글자·음식·사람 없음), 하루 30장 한도 |

모델은 `.env`에서 바꿀 수 있습니다. 모델별 품질·비용 비교는 [개발진행.md](개발진행.md) 8절에 있습니다.

### 화면 (웹 앱, 휴대폰 홈 화면에 설치 가능)

홈·지도·일정·내 가게 화면은 **AI를 거치지 않고** 의사결정 모델을 바로 부릅니다 (AI 비용 0). AI Agent는 '대화'와 '만들기'에서만 씁니다.

| 여행객 | 사장님 |
|---|---|
| **홈**: 동네별 혼잡, 추천 식당 카드(점수 구성), 내 주변 3km 추천, 찜한 가게 | **내 가게**: 네이버 등록 상태, 손님 많은 요일·시간, 유동인구 구성, 요일×시간 혼잡, 리뷰 요약, 동네 새로 생긴 가게, 리뷰 붙여넣기 분석 |
| **지도**: 동네 혼잡, 관광지·오름·해수욕장·명소, 식당 (확대 단계별 표시) | **만들기**: 홍보 이미지, 메뉴판(사진), 오늘의 메뉴, 네이버 등록 자료 |
| **일정**: 덜 붐비는 순서, 실제 길찾기 시간, 직접 고치기(순서·빼기·추가·머무는 시간), 공유 | **지도** |
| **대화**: AI Agent, 결과를 카드·막대·일정표로 표시, 음성 입력 | **대화**: 미리보기 이미지에 "확정 / 고쳐 주세요" 버튼 |

---

## 2. 설치·실행

### 실행 환경

- Windows 10/11 또는 Linux, **Python 3.11**, 인터넷 연결 (Claude API·네이버 API 호출)
- 빅데이터센터 PC 사양(i7-8700 / GTX 1060 / RAM 32GB)에서 실행 가능합니다. LLM은 외부 API를 쓰고 리뷰 감성 모델은 미리 계산해 두므로 **GPU가 필요 없습니다**.
- 데이터는 로컬 SQLite 파일 하나(`data/processed/jeju.db`)에 들어 있습니다.

### 빠른 실행 (처리된 DB가 함께 제공된 경우)

```bash
pip install -r requirements.txt
python -m playwright install chromium     # 메뉴판·홍보 카드 이미지 그리기용
copy .env.example .env                    # (Linux: cp) 그 뒤 .env 에 API 키 입력
uvicorn app.api.main:app --port 8000      # 브라우저에서 http://localhost:8000
```

터미널에서 바로 대화할 수도 있습니다.

```bash
python scripts/chat.py --mode owner       # 사장님
python scripts/chat.py --mode tourist     # 관광객
```

### API 키 (`.env`)

[.env.example](.env.example)을 복사해 채웁니다. **`.env`는 제출물·저장소에 넣지 않습니다.**

| 변수 | 필수 | 없으면 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 대화·만들기에 필수 | 홈·지도·일정·내 가게는 동작, 대화만 안 됨 |
| `NCP_CLIENT_ID`, `NCP_CLIENT_SECRET` | 선택 | 일정 이동 시간이 직선거리 추정으로 바뀜 |
| `NAVER_SEARCH_CLIENT_ID`, `NAVER_SEARCH_CLIENT_SECRET` | 선택 | 새 가게의 네이버 등록 확인 불가 (이미 확인한 2,779곳은 DB 결과 사용) |
| `GEMINI_API_KEY` | 선택 | 홍보 이미지가 기본 배경으로 만들어짐 |
| `CLAUDE_MODEL_OWNER`, `CLAUDE_MODEL_TOURIST` | 선택 | 사용자 유형별 모델 지정 |
| `DEMO_ACCESS_CODE`, `DEMO_DAILY_LIMIT` | 선택 | 공개 데모에서 AI 대화에 접속 코드·하루 한도 적용 |

### 데이터부터 다시 만들기

제주데이터허브에서 받은 CSV를 `data/raw/<데이터ID>/`에 넣은 뒤 실행합니다. 순서와 처리 내용은 [데이터 활용 명세](docs/데이터활용명세.md)에 있습니다.

```bash
python scripts/check_data.py              # 빠진 데이터 확인
python scripts/fetch_hub_api.py           # API형 데이터 수집 (583, 591, 592, 811, 837)
python scripts/build_store_db.py          # 음식점 인허가 → jeju.db
python scripts/build_insight_db.py        # 분석용 테이블
python scripts/build_pois.py              # 관광 장소 + 월별 혼잡
python scripts/geocode_regions.py         # 읍면동 중심 좌표 (NCP 키)
python scripts/geocode_stores.py          # 가게 좌표 (NCP 키)
python scripts/check_naver.py 애월         # 네이버 등록 여부 (검색 키)
python scripts/train_demand.py            # 방문 수요 예측 모델 학습·검증
pip install -r requirements-ml.txt        # (선택) PyTorch CPU·transformers
python scripts/build_review_sentiment.py  # 리뷰 감성 미리 계산
python scripts/sync_licenses.py 새파일.csv  # 이후 인허가 갱신분만 반영
```

### 데모 배포

```bash
gcloud run deploy je-ju --source . --region asia-northeast3   # 서버 (Cloud Run)
python scripts/deploy_firebase.py                              # 화면 (Firebase Hosting, config.js에 서버 주소)
```

### 검증

```bash
python -m pytest -q                       # 단위 테스트 57개 (API 키 불필요)
python scripts/eval_agent.py              # Agent 시나리오 평가 16개 (API 비용 약 $0.5) → docs/eval_results.json
python scripts/eval_agent.py --model claude-haiku-5-5   # 한 모델로 비교
```

---

## 3. 검증 결과

| 대상 | 방법 | 결과 |
|---|---|---|
| Agent | 시나리오 15개 자동 평가: 필요한 도구 호출, 승인 전 확정 금지, 근거 표기, 답의 숫자가 도구 결과에 있는지, 메뉴 가격 정확도 | **15/15 통과** (2026-11-10, 사장님 10 · 관광객 4 · 범위 밖 1, [docs/eval_results.json](docs/eval_results.json)). 이전 평가에서 찾은 문제 3건 수정 후 재평가 ([개발진행.md](개발진행.md) 12절). 비용 시나리오당 약 $0.036 |
| 방문 수요 예측 | 2025-08~2026-02 학습, 2026-03~04 검증 | 오차(MAPE) 18.9% (요일 평균 방식 22.8%), 혼잡 등급 일치 59.4% (36.9%) |
| 리뷰 감성 | 오픈소스 모델 vs 규칙 | 5,309개 절에서 일치율 90%, 사람 검증 표본 100건 비교 ([docs/검증](docs/검증)) |
| 네이버 등록 판별 | 표본 50건 사람 확인 | [docs/검증](docs/검증) |

---

## 4. 오류·제약

- **혼잡은 실시간이 아닙니다.** 과거 유동인구·카드·외식업 패턴으로 예측합니다. 화면과 답에 항상 표시합니다.
- **유동인구(583)는 하루 누적 집계값**이라 사람 수가 아니라 비율로만 씁니다.
- **인허가는 폐업 신고를 안 하면 '영업'으로 남습니다.** 그래서 네이버 등록·주소 일치로 영업 가능성을 표시하고("영업 확인 / 방문 전 확인"), 사용자가 "문 닫았어요"로 알릴 수 있습니다.
- **인허가일은 주인·상호가 바뀌어도 이어질 수 있어** '개업 N년'이 아닌 '인허가 기준 N년'으로 표시합니다.
- 해수욕장 계절음식점·마을 단체 이름의 인허가는 추천에서 뺍니다.
- 구글 리뷰(903)는 2021년 자료이고 일부 가게만 있습니다. 리뷰가 없는 가게는 사장님이 붙여넣은 리뷰나 사장님 말씀을 근거로 씁니다.
- 시간대 패턴(490)은 코로나 이전 2019년 자료에 최근 카드 데이터(502)로 보정합니다 (결정 D-01).
- 공휴일은 학습 표본이 적어 일요일 패턴으로 대신 예측합니다.
- 사업자(인허가) 상호와 간판·네이버 상호가 다른 가게가 많습니다. 상호 앞부분·동네+업종·**도로명 주소**로도 검색해 같은 주소의 가게를 찾고, 사장님께 "이 가게가 맞나요?"를 확인받아 연결합니다. 이름이 완전히 달라도 사장님이 네이버 상호를 알려 주면 **주소가 같을 때만** 연결합니다 (남의 가게에 잘못 연결되지 않게). AI는 등록 자료를 만들기 전에 다른 이름으로 이미 등록됐는지 먼저 묻습니다.
- 인터넷이 끊기면 AI 대화·길찾기·네이버 확인이 멈춥니다. 홈·지도·일정 계산(직선거리 추정)은 로컬 DB로 동작합니다.

| 화면에 보이는 오류 | 원인·조치 |
|---|---|
| "Claude API 키가 설정되지 않았습니다" | `.env`에 `ANTHROPIC_API_KEY` 입력 후 서버 다시 시작 |
| 접속 코드를 묻는 창 | 공개 데모에 `DEMO_ACCESS_CODE`가 설정됨. 운영자에게 코드 문의 |
| "오늘 데모 사용량이 다 찼습니다" | `DEMO_DAILY_LIMIT` 도달. 다음 날 초기화 |
| 이동 시간이 "직선 추정"으로 나옴 | NCP 키가 없거나 길찾기 API 오류 (권한 오류면 10분 동안 다시 시도하지 않음) |
| "위치를 받지 못했어요" | 브라우저 위치 권한 거절 또는 https가 아닌 주소. 동네를 골라 찾으면 됨 |
| "이전 질문을 처리하는 중입니다" | 한 대화에서 답이 끝나기 전에 또 보냄. 답이 끝난 뒤 다시 보내기 |
| "사진은 5MB 이하로 올려 주세요" | 사진을 줄이거나 jpg·png·webp로 올리기 |

---

## 5. 개인정보·보안

- API 키는 `.env`에만 두고 저장소·제출물·화면·영상에 넣지 않습니다.
- 리뷰 데이터의 작성자 이름·등급·사진 주소는 전처리에서 지웁니다.
- 사장님이 붙여넣은 리뷰는 분석만 하고 저장하지 않습니다.
- 내 위치는 버튼을 누를 때 한 번만, **약 100m 단위로 줄여서** 쓰고 저장하지 않습니다.
- 찜 목록은 사용자 기기(브라우저)에만 저장합니다. 로그인이 없습니다.
- 허브 원본·처리 데이터는 공개 저장소에 올리지 않습니다 (`.gitignore`).

---

## 6. AI 사용 범위 공개

| 쓰임 | 도구 | 범위 |
|---|---|---|
| 서비스 실행 중 | Claude API (Anthropic) | Agent 판단·도구 선택, 답 작성, 메뉴판 사진 읽기 |
| 서비스 실행 중 | Gemini API (Google) | 홍보 카드 **배경** 이미지 생성만. 글자·가격은 템플릿으로 그림 |
| 데이터 준비 | KoELECTRA 감성 모델 (오픈소스) | 리뷰 감성 미리 계산 |
| 개발 | Claude Code (Anthropic) | 코드 작성·수정, 테스트·평가 스크립트 작성, 문서 초안. 기획 방향·기능 결정·결과 확인은 참가자가 함 |

외부 API·오픈소스 전체 목록과 이용조건은 [데이터 활용 명세](docs/데이터활용명세.md)에 있습니다.

---

## 7. 폴더

```
app/
  agent/    loop.py (Agent 루프) · tools.py (도구 정의·입력 검증·승인 가드) · prompts.py (시스템 프롬프트)
  tools/    stores · insight · forecast · recommend · places · route · naver · reviews · marketing · drafts · cards · imagegen · listing
  data/     db.py (SQLite) · regions.py (법정동 ↔ 행정동 대응표)
  api/      main.py (FastAPI, SSE 스트리밍)
  static/   index.html · app.css · app.js (웹 앱, PWA)
  templates/ 메뉴판·홍보 카드 HTML 템플릿
data/       raw (허브 원본, 저장소 제외) · processed (jeju.db, 수요 예측 모델) · sample
scripts/    수집·전처리·학습 · chat.py (터미널 대화) · eval_agent.py (시나리오 평가)
tests/      pytest (API 키 없이 실행)
docs/       사용자 매뉴얼 · 데이터 활용 명세 · 평가 결과 · 검증 표본
```
