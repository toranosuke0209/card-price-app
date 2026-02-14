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
REM [1/5] EC2 shops: new arrivals page (cardrush, tierone, hobbystation, batosuki, fullahead)
REM ================================================
echo [1/5] EC2 shops: crawling new arrivals pages...
ssh -i "!PEM_PATH!" -o StrictHostKeyChecking=no !EC2_HOST! "cd /home/ubuntu/project/backend && /home/ubuntu/project/backend/venv/bin/python batch_crawl.py --new-arrivals --shop all --pages 10"

if errorlevel 1 (
    echo WARNING: EC2 new arrivals had errors, continuing...
)
echo.

REM ================================================
REM [2/5] Yuyutei: crawl locally (latest sets + new arrivals)
REM ================================================
echo [2/5] Yuyutei: crawling latest sets locally...
python crawl_yuyutei.py --sets bs75 bs74 bs73 bsc51 bsc50 sd70 sd69 new sale

if errorlevel 1 (
    echo WARNING: Yuyutei crawl failed, continuing...
)

REM Get latest yuyutei JSON file
set YYT_FILE=
for /f "delims=" %%i in ('dir /b /o-d output\yuyutei_*.json 2^>nul') do (
    set "YYT_FILE=output\%%i"
    set "YYT_FILENAME=%%i"
    goto :yyt_found
)
echo WARNING: Yuyutei JSON file not found, skipping upload
goto :yyt_skip

:yyt_found
echo Latest file: !YYT_FILE!

REM ================================================
REM [3/5] Upload & import yuyutei data on EC2
REM ================================================
echo [3/5] Uploading and importing yuyutei data on EC2...

scp -i "!PEM_PATH!" -o StrictHostKeyChecking=no "!YYT_FILE!" !EC2_HOST!:/home/ubuntu/project/data/

if errorlevel 1 (
    echo WARNING: Yuyutei upload failed, continuing...
    goto :yyt_skip
)

ssh -i "!PEM_PATH!" -o StrictHostKeyChecking=no !EC2_HOST! "cd /home/ubuntu/project/backend && /home/ubuntu/venv/bin/python ../local/import_yuyutei.py --input /home/ubuntu/project/data/!YYT_FILENAME!"

if errorlevel 1 (
    echo WARNING: Yuyutei import failed, continuing...
)

:yyt_skip
echo.

REM ================================================
REM [4/5] Dorasuta: crawl locally (latest series only)
REM ================================================
echo [4/5] Dorasuta: crawling new arrivals locally...
python crawl_dorasuta.py --new-arrivals --pages 5

if errorlevel 1 (
    echo WARNING: Dorasuta crawl failed, continuing...
)

REM Get latest dorasuta JSON file
set DRS_FILE=
for /f "delims=" %%i in ('dir /b /o-d output\dorasuta_*.json 2^>nul') do (
    set "DRS_FILE=output\%%i"
    set "DRS_FILENAME=%%i"
    goto :drs_found
)
echo WARNING: Dorasuta JSON file not found, skipping upload
goto :drs_skip

:drs_found
echo Latest file: !DRS_FILE!

REM ================================================
REM [5/5] Upload & import dorasuta data on EC2
REM ================================================
echo [5/5] Uploading and importing dorasuta data on EC2...

scp -i "!PEM_PATH!" -o StrictHostKeyChecking=no "!DRS_FILE!" !EC2_HOST!:/home/ubuntu/project/data/

if errorlevel 1 (
    echo WARNING: Dorasuta upload failed, continuing...
    goto :drs_skip
)

ssh -i "!PEM_PATH!" -o StrictHostKeyChecking=no !EC2_HOST! "cd /home/ubuntu/project/backend && /home/ubuntu/venv/bin/python ../local/import_dorasuta.py --input /home/ubuntu/project/data/!DRS_FILENAME!"

if errorlevel 1 (
    echo WARNING: Dorasuta import failed, continuing...
)

:drs_skip
echo.

echo ================================================
echo New Arrivals Batch Done: %date% %time%
echo   - EC2 shops (5 shops): new arrivals pages
echo     cardrush: /new
echo     tierone: /view/category/bs75
echo     hobbystation: BS75 category
echo     batosuki: BS75 category
echo     fullahead: /shopbrand/bs75/
echo   - Yuyutei: latest sets (bs75,bs74,bs73,etc.)
echo   - Dorasuta: new arrivals (?st0=1) 5 pages
echo ================================================
pause
