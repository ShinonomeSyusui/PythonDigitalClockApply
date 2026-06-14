@echo off
setlocal

set APP_NAME=SevenSegmentClock
for /f "usebackq delims=" %%i in (`python -c "from version import APP_VERSION; print(APP_VERSION)"`) do set VERSION=%%i
set RELEASE_ROOT=release
set RELEASE_DIR=%RELEASE_ROOT%\_%APP_NAME%-v%VERSION%-staging-%RANDOM%
set ZIP_PATH=%RELEASE_ROOT%\%APP_NAME%-v%VERSION%.zip

set NO_PAUSE=1
call build.bat
if errorlevel 1 (
    echo Build failed. Release package was not created.
    pause
    exit /b 1
)

if not exist "%RELEASE_ROOT%" mkdir "%RELEASE_ROOT%"
if exist "%ZIP_PATH%" del "%ZIP_PATH%"

mkdir "%RELEASE_DIR%"
copy "dist\%APP_NAME%.exe" "%RELEASE_DIR%\" >nul
copy "README.md" "%RELEASE_DIR%\" >nul
copy "LICENSE" "%RELEASE_DIR%\" >nul
copy "CHANGELOG.md" "%RELEASE_DIR%\" >nul
if exist "NOTICE.md" copy "NOTICE.md" "%RELEASE_DIR%\" >nul
if exist "docs" xcopy "docs" "%RELEASE_DIR%\docs\" /e /i /y >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%RELEASE_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force"
if errorlevel 1 (
    echo Failed to create release zip.
    pause
    exit /b 1
)

rmdir /s /q "%RELEASE_DIR%" >nul 2>nul

echo Release package complete: %ZIP_PATH%
pause
