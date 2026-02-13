@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ================================================
echo New Arrivals Batch Start: %date% %time%
echo ================================================

REM Check config file
if not exist "config.txt" (
    echo ERROR: config.txt not found
    echo Please create config.txt with:
    echo   PEM_PATH=C:\path\to\your-key.pem
    echo   EC2_HOST=ubuntu@your-ec2-ip
    pause
    exit /b 1
)

REM Load config
for /f "tokens=1,2 delims==" %%a in (config.txt) do (
    if "%%a"=="PEM_PATH" set "PEM_PATH=%%b"
    if "%%a"=="EC2_HOST" set "EC2_HOST=%%b"
)

if "!PEM_PATH!"=="" (
    echo ERROR: PEM_PATH not set in config.txt
    pause
    exit /b 1
)

if "!EC2_HOST!"=="" (
    echo ERROR: EC2_HOST not set in config.txt
    pause
    exit /b 1
)

echo Config loaded:
echo   PEM: !PEM_PATH!
echo   HOST: !EC2_HOST!
echo.

REM ================================================
REM [1] EC2 shops: new arrivals (cardrush, tierone, hobbystation, batosuki, fullahead)
REM ================================================
echo [1/3] EC2 shops: new arrivals...
ssh -i "!PEM_PATH!" -o StrictHostKeyChecking=no !EC2_HOST! "cd /home/ubuntu/project/backend && /home/ubuntu/project/backend/venv/bin/python batch_crawl.py --new-arrivals --shop all"

if errorlevel 1 (
    echo WARNING: EC2 new arrivals had errors, continuing...
)
echo.

REM ================================================
REM [2] Yuyutei: crawl locally (new arrivals only)
REM ================================================
echo [2/3] Yuyutei: crawling new arrivals locally...
python crawl_yuyutei.py --new-arrivals

if errorlevel 1 (
    echo Yuyutei crawl failed
    pause
    exit /b 1
)

REM Get latest JSON file
set LATEST_FILE=
for /f "delims=" %%i in ('dir /b /o-d output\yuyutei_*.json 2^>nul') do (
    set "LATEST_FILE=output\%%i"
    set "FILENAME=%%i"
    goto :found
)
echo JSON file not found
pause
exit /b 1

:found
echo Latest file: !LATEST_FILE!

REM ================================================
REM [3] Upload & import yuyutei data on EC2
REM ================================================
echo [3/3] Uploading and importing yuyutei data on EC2...

REM Upload to EC2
scp -i "!PEM_PATH!" -o StrictHostKeyChecking=no "!LATEST_FILE!" !EC2_HOST!:/home/ubuntu/project/data/

if errorlevel 1 (
    echo Upload failed
    pause
    exit /b 1
)

REM Import on EC2
ssh -i "!PEM_PATH!" -o StrictHostKeyChecking=no !EC2_HOST! "cd /home/ubuntu/project/backend && /home/ubuntu/venv/bin/python ../local/import_yuyutei.py --input /home/ubuntu/project/data/!FILENAME!"

if errorlevel 1 (
    echo Import failed
    pause
    exit /b 1
)

echo.
echo ================================================
echo New Arrivals Batch Done: %date% %time%
echo   - EC2 shops (5 shops): completed
echo   - Yuyutei: crawled, uploaded, imported
echo ================================================
pause
