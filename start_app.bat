@echo off
chcp 65001 >nul
title 퇴사자 처리 자동화
cd /d "%~dp0"

echo ============================================
echo   퇴사자 처리 자동화 - 시작 중...
echo ============================================
echo.

REM 3초 뒤 브라우저에 앱 화면을 자동으로 연다 (서버가 뜰 시간을 준다)
start "" /min cmd /c "timeout /t 3 >nul & start "" http://127.0.0.1:5000"

REM python 이 없으면 py 로 실행
where python >nul 2>nul
if %errorlevel%==0 (
    python app.py
) else (
    py app.py
)

echo.
echo 앱이 종료되었습니다. 창을 닫아도 됩니다.
pause
