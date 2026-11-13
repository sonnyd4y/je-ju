@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [제주 동네가게 AI Agent] 실행 준비
python --version >nul 2>&1 || (echo Python 3.11 이 필요합니다. https://www.python.org/downloads/ 에서 설치 후 다시 실행하세요. & pause & exit /b 1)
if not exist .venv (
  echo 1/3 가상환경 만드는 중...
  python -m venv .venv || (pause & exit /b 1)
)
call .venv\Scripts\activate.bat
if not exist .venv\.installed (
  echo 2/3 라이브러리 설치 중 ^(처음 한 번, 5~10분^)...
  python -m pip install -q --upgrade pip
  pip install -r requirements-lock.txt || (pause & exit /b 1)
  python -m playwright install chromium || (pause & exit /b 1)
  echo ok> .venv\.installed
)
if not exist .env copy .env.example .env >nul
echo 3/3 서버 시작: http://localhost:8000  ^(끄려면 이 창에서 Ctrl+C^)
start "" /min cmd /c "timeout /t 10 >nul & start http://localhost:8000"
python -m uvicorn app.api.main:app --port 8000
pause
