@echo off
chcp 65001 >nul
title 퇴사자 처리 자동화
cd /d "%~dp0"

echo ============================================
echo   퇴사자 처리 자동화
echo ============================================
echo.

REM python 또는 py 선택
where python >nul 2>nul
if %errorlevel%==0 ( set PY=python ) else ( set PY=py )

REM ---- 1) 최신 코드 자동 업데이트 ----
where git >nul 2>nul
if %errorlevel%==0 (
    echo [1/2] 최신 버전 확인 중...
    git pull
    REM 새 패키지가 추가됐을 수 있어 조용히 설치 확인 (이미 있으면 즉시 통과)
    %PY% -m pip install -q -r requirements.txt 2>nul
) else (
    echo [1/2] git 이 없어 자동 업데이트를 건너뜁니다.
)
echo.

REM ---- 2) 앱 실행 + 브라우저 자동 열기 ----
echo [2/2] 앱을 시작합니다...
start "" /min cmd /c "timeout /t 3 >nul & start "" http://127.0.0.1:5000"

%PY% app.py

echo.
echo 앱이 종료되었습니다. 창을 닫아도 됩니다.
pause
