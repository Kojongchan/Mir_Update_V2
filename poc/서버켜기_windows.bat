@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   PoC 3D 뷰어 서버를 켭니다.
echo   [중요] 이 검은 창은 닫지 마세요. 닫으면 서버도 꺼집니다.
echo.
echo   서버가 켜지면 크롬에서 아래 주소를 여세요:
echo.
echo        http://localhost:8099/index.html
echo.
echo   (끝낼 때는 이 창에서 Ctrl+C 또는 창 닫기)
echo ============================================================
echo.

REM 파이썬이 있으면 파이썬으로, 없으면 Node 로 서버 실행
py -m http.server 8099 2>nul
if %errorlevel%==0 goto :eof
python -m http.server 8099 2>nul
if %errorlevel%==0 goto :eof
python3 -m http.server 8099 2>nul
if %errorlevel%==0 goto :eof

echo.
echo [!] Python 을 찾지 못했습니다. 아래 중 하나를 하세요:
echo     1) https://www.python.org/downloads/  에서 Python 설치 후 이 파일 다시 더블클릭
echo     2) Node.js 가 있으면 이 폴더에서:  npx http-server -p 8099 -c-1
echo.
pause
