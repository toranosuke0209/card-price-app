@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ================================================
echo Dorasuta Special (SALE/傷あり特価) Crawler
echo Start: %date% %time%
echo ================================================

REM Check config file
if not exist "config.txt" (
    echo ERROR: config.txt not found
    pause
    exit /b 1
)

REM Load config
for /f "tokens=1,2 delims==" %%a in (config.txt) do (
    if "%%a"=="PEM_PATH" set "PEM_PATH=%%b"
    if "%%a"=="EC2_HOST" set "EC2_HOST=%%b"
)

echo.
echo Crawling SALE and Damaged items...
echo.

REM Crawl special pages
python crawl_dorasuta.py --special
if errorlevel 1 (
    echo Crawl failed
    pause
    exit /b 1
)

REM Get latest special JSON file
set LATEST_FILE=
for /f "delims=" %%i in ('dir /b /o-d output\dorasuta_special_*.json 2^>nul') do (
    set "LATEST_FILE=output\%%i"
    set "FILENAME=%%i"
    goto :found
)
echo JSON file not found
pause
exit /b 1

:found
echo Latest file: !LATEST_FILE!

REM Upload to EC2
echo Uploading to EC2...
scp -i "!PEM_PATH!" -o StrictHostKeyChecking=no "!LATEST_FILE!" !EC2_HOST!:/home/ubuntu/project/data/

if errorlevel 1 (
    echo Upload failed
    pause
    exit /b 1
)

REM Import on EC2
echo Importing on EC2...
ssh -i "!PEM_PATH!" -o StrictHostKeyChecking=no !EC2_HOST! "cd /home/ubuntu/project/backend && /home/ubuntu/venv/bin/python ../local/import_dorasuta.py --input /home/ubuntu/project/data/!FILENAME!"

if errorlevel 1 (
    echo Import failed
    pause
    exit /b 1
)

echo ================================================
echo Done: %date% %time%
echo ================================================
pause
