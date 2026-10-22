@echo off
setlocal

set "APP_DIR=%~dp0lob\wealth\portfolio-manager"
set "PYTHON=%APP_DIR%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo ERROR: Python virtual environment not found:
    echo   %PYTHON%
    echo Create the project virtual environment before starting the test.
    exit /b 1
)

pushd "%APP_DIR%"
if errorlevel 1 (
    echo ERROR: Could not open the application directory.
    exit /b 1
)

set "CHAT_API_URL=http://127.0.0.1:8989"

echo Connecting the test harness to the local API at %CHAT_API_URL%
echo Start startapi.bat first if the API is not already running.
echo.

"%PYTHON%" a365_verify.py %*
set "EXIT_CODE=%ERRORLEVEL%"

popd
exit /b %EXIT_CODE%
