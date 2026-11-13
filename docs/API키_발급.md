# API 키 발급·설정 방법

키는 프로젝트 폴더의 `.env` 파일에 넣습니다. `.env.example`을 `.env`로 복사한 뒤 값을 채우고 서버를 다시 시작하세요.

```bash
copy .env.example .env      # Linux: cp .env.example .env
```

**처리된 데이터(`data/processed/jeju.db`)가 있으면 키가 하나도 없어도** 홈·지도·일정·내 가게 화면은 동작합니다. 키는 아래 기능을 켤 때만 필요합니다.

| 변수 | 켜지는 기능 | 없으면 | 필요성 |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | AI 대화, 만들기(홍보·메뉴판), 메뉴판 사진 읽기 | 대화·만들기만 안 됨 | **AI Agent 확인에 필수** |
| `GEMINI_API_KEY` | 홍보 카드의 생성형 제주 배경 | 기본 배경으로 그림 | 선택 |
| `NCP_CLIENT_ID`, `NCP_CLIENT_SECRET` | 일정의 실제 길찾기 이동 시간, 주소 → 좌표 | 직선거리로 추정 | 선택 |
| `NAVER_SEARCH_CLIENT_ID`, `NAVER_SEARCH_CLIENT_SECRET` | 새 가게의 네이버 지도 등록 확인·다른 상호 연결 | 이미 확인한 2,779곳만 DB 결과로 표시 | 선택 |
| `JEJUDATAHUB_PROJECT_KEY` | 허브 API형 데이터 다시 받기 (`scripts/fetch_hub_api.py`) | 데이터 재수집 불가 (실행에는 영향 없음) | 데이터부터 다시 만들 때만 |

## 1. Claude (Anthropic) — `ANTHROPIC_API_KEY`

1. https://console.anthropic.com 에 가입·로그인
2. **Settings → Billing**에서 크레딧 충전
3. **Settings → Limits**에서 월 사용 한도 설정 (평가용 키는 반드시 한도 설정)
4. **API Keys → Create Key** → 만든 키를 `.env`의 `ANTHROPIC_API_KEY=`에 붙여넣기

모델은 기본값(사장님 `claude-sonnet-5-5`, 관광객 `claude-haiku-5-5`)을 쓰며, `CLAUDE_MODEL_OWNER`, `CLAUDE_MODEL_TOURIST`로 바꿀 수 있습니다.
비용: 관광객 대화 한 번 약 $0.002, 사장님 대화 한 번 약 $0.03~0.05, 전체 평가 16개 약 $0.6.

## 2. Google Gemini — `GEMINI_API_KEY` (선택)

1. https://aistudio.google.com 로그인 → **Get API key → Create API key**
2. `.env`의 `GEMINI_API_KEY=`에 붙여넣기
3. 하루 생성 장수는 `GEMINI_DAILY_LIMIT`(기본 30장)로 제한됩니다.

## 3. 네이버 클라우드 플랫폼 Maps — `NCP_CLIENT_ID`, `NCP_CLIENT_SECRET` (선택)

1. https://console.ncloud.com 로그인 → **Services → Application Services → Maps**
2. **Application 등록** → 사용 API에서 **Directions 5**, **Geocoding** 선택
3. 인증 정보의 Client ID / Client Secret을 `.env`에 입력

## 4. 네이버 검색 API — `NAVER_SEARCH_CLIENT_ID`, `NAVER_SEARCH_CLIENT_SECRET` (선택)

1. https://developers.naver.com 로그인 → **Application → 애플리케이션 등록**
2. 사용 API에서 **검색** 선택, 환경은 WEB(`http://localhost`)
3. Client ID / Client Secret을 `.env`에 입력 (하루 호출 한도 25,000회)

## 5. 제주데이터허브 — `JEJUDATAHUB_PROJECT_KEY` (데이터 재수집 때만)

1. https://www.jejudatahub.net 로그인 → 필요한 데이터 이용 신청
2. **마이페이지 → 프로젝트**에서 프로젝트 키 확인 → `.env`에 입력

## 6. 공개 데모 운영용 (선택)

| 변수 | 뜻 |
|---|---|
| `DEMO_ACCESS_CODE` | 정하면 AI 대화에 접속 코드를 물음 |
| `DEMO_DAILY_LIMIT` | 하루 AI 대화 한도 (기본 300) |

## 키 관리

- `.env`는 저장소에 올라가지 않습니다 (`.gitignore`).
- 평가용으로 제출한 키는 사용 한도를 걸어 두었고, **평가 기간이 끝나면 삭제·폐기**합니다 (대회 규칙).
