@echo off
setlocal

set "APP_DIR=%~dp0lob\wealth\ai-agent-starter-portfolio-manager"
set "PYTHON=%APP_DIR%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo ERROR: Python virtual environment not found:
    echo   %PYTHON%
    echo Create the project virtual environment before starting the chat.
    exit /b 1
)

pushd "%APP_DIR%"

set "CHAT_API_URL=http://127.0.0.1:8989"

echo Connecting the console to the local API at %CHAT_API_URL%
echo Start startapi.bat first if the API is not already running.
echo.

"%PYTHON%" chat.py
set "EXIT_CODE=%ERRORLEVEL%"

popd
exit /b %EXIT_CODE%