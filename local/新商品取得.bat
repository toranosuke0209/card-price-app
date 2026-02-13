@echo off
REM デスクトップに置いて使うショートカット
REM local\new_arrivals.bat を呼び出す

cd /d "%~dp0"

REM このファイルがlocal/にある場合はそのまま実行
if exist "new_arrivals.bat" (
    call new_arrivals.bat
    exit /b
)

REM デスクトップ等に置いた場合はlocal/を探す
if exist "%~dp0local\new_arrivals.bat" (
    cd /d "%~dp0local"
    call new_arrivals.bat
    exit /b
)

REM リポジトリのパスを指定（環境に合わせて変更）
set "PROJECT_DIR=C:\Users\toraa\project\local"
if exist "%PROJECT_DIR%\new_arrivals.bat" (
    cd /d "%PROJECT_DIR%"
    call new_arrivals.bat
    exit /b
)

echo ERROR: new_arrivals.bat が見つかりません
echo このファイルを local\ フォルダに置くか、PROJECT_DIR を編集してください
pause
