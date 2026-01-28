@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ================================================
echo Yuyutei Crawler Start: %date% %time%
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

REM Crawl
python crawl_yuyutei.py --sets bs74
if errorlevel 1 (
    echo Crawl failed
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
ssh -i "!PEM_PATH!" -o StrictHostKeyChecking=no !EC2_HOST! "cd /home/ubuntu/project/backend && /home/ubuntu/venv/bin/python ../local/import_yuyutei.py --input /home/ubuntu/project/data/!FILENAME!"

if errorlevel 1 (
    echo Import failed
    pause
    exit /b 1
)

echo ================================================
echo Done: %date% %time%
echo ================================================
pause
