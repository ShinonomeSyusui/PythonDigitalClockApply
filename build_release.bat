@echo off
setlocal

set APP_NAME=SevenSegmentClock
set VERSION=1.3.0
set RELEASE_ROOT=release
set RELEASE_DIR=%RELEASE_ROOT%\%APP_NAME%-v%VERSION%
set ZIP_PATH=%RELEASE_ROOT%\%APP_NAME%-v%VERSION%.zip

set NO_PAUSE=1
call build.bat
if errorlevel 1 (
    echo Build failed. Release package was not created.
    pause
    exit /b 1
)

if not exist "%RELEASE_ROOT%" mkdir "%RELEASE_ROOT%"
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
if exist "%ZIP_PATH%" del "%ZIP_PATH%"

mkdir "%RELEASE_DIR%"
copy "dist\%APP_NAME%.exe" "%RELEASE_DIR%\" >nul
copy "README.md" "%RELEASE_DIR%\" >nul
copy "LICENSE" "%RELEASE_DIR%\" >nul
copy "CHANGELOG.md" "%RELEASE_DIR%\" >nul
if exist "docs" xcopy "docs" "%RELEASE_DIR%\docs\" /e /i /y >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%RELEASE_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force"
if errorlevel 1 (
    echo Failed to create release zip.
    pause
    exit /b 1
)

echo Release package complete: %ZIP_PATH%
pause
