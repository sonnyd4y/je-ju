# 데모 서버 (Google Cloud Run). 센터 PC 실행은 README의 로컬 설치 절차를 따른다.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# 카드 이미지의 한글 글꼴
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt \
    && playwright install --with-deps chromium

COPY app ./app
COPY data/processed/jeju.db data/processed/demand_model.joblib data/processed/demand_metrics.json ./data/processed/

ENV PORT=8080
CMD exec uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT}
