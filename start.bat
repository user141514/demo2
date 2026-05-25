@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "ACTIVATE_BAT=E:\Anaconda3\Scripts\activate.bat"

if not exist "%ACTIVATE_BAT%" (
  echo [ERROR] Cannot find conda activate script: %ACTIVATE_BAT%
  exit /b 1
)

call "%ACTIVATE_BAT%" rag-env
if errorlevel 1 (
  echo [ERROR] Failed to activate conda environment: rag-env
  exit /b 1
)

cd /d "%ROOT_DIR%"
set "SCORING_APP_DEBUG=0"
set "SCORING_APP_HOST=127.0.0.1"
set "SCORING_APP_PORT=5000"

python -c "import flask, openai, requests, PIL" >nul 2>&1
if errorlevel 1 (
  echo [INFO] Installing missing runtime dependencies into rag-env...
  python -m pip install -r "%ROOT_DIR%requirements.txt"
  if errorlevel 1 (
    echo [ERROR] Failed to install runtime dependencies.
    exit /b 1
  )
)

echo [INFO] Starting app with Python:
python -c "import sys; print(sys.executable)"

python app.py
exit /b %errorlevel%
