@echo off
chcp 65001 >nul
title 퇴사자 처리 자동화 - 최초 설치
cd /d "%~dp0"

echo ============================================
echo   최초 1회 설치를 진행합니다 (몇 분 걸려요)
echo ============================================
echo.

where python >nul 2>nul
if %errorlevel%==0 (
    set PY=python
) else (
    set PY=py
)

echo [1/2] 필요한 패키지 설치 중...
%PY% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo *** 패키지 설치에 실패했습니다. 위 메시지를 확인해 주세요. ***
    pause
    exit /b 1
)

echo.
echo [2/2] 자동화용 브라우저(Chromium) 설치 중...
%PY% -m playwright install chromium
if %errorlevel% neq 0 (
    echo.
    echo *** 브라우저 설치에 실패했습니다. 위 메시지를 확인해 주세요. ***
    pause
    exit /b 1
)

echo.
echo ============================================
echo   설치 완료! 이제 start_app.bat 을 실행하세요.
echo ============================================
pause
