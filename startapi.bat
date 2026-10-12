@echo off
setlocal

set "APP_DIR=%~dp0lob\wealth\ai-agent-starter-portfolio-manager"
set "PYTHON=%APP_DIR%\.venv\Scripts\python.exe"
set "APIM_HOST=apim-c4fhgayvfr3b2.azure-api.net"
set "APIM_PRIVATE_IP=10.100.2.4"

if not exist "%PYTHON%" (
    echo ERROR: Python virtual environment not found:
    echo   %PYTHON%
    echo Create the project virtual environment before starting the API.
    exit /b 1
)

where docker >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not available on PATH.
    exit /b 1
)

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$entry = [System.Net.Dns]::GetHostAddresses('%APIM_HOST%') | Where-Object AddressFamily -eq InterNetwork | Select-Object -ExpandProperty IPAddressToString -First 1; $entry"`) do set "APIM_RESOLVED_IP=%%I"
if not "%APIM_RESOLVED_IP%"=="%APIM_PRIVATE_IP%" (
    echo ERROR: %APIM_HOST% does not resolve to %APIM_PRIVATE_IP%.
    echo Add this line to C:\Windows\System32\drivers\etc\hosts as Administrator:
    echo   %APIM_PRIVATE_IP% %APIM_HOST%
    echo Then run this launcher again.
    exit /b 1
)

pushd "%APP_DIR%"

echo Stopping the Docker API container if it is running...
docker compose stop ai-agent-starter-api >nul

echo Starting PostgreSQL in Docker...
docker compose up -d ai-agent-starter-portfolio-manager-postgres
if errorlevel 1 (
    echo ERROR: PostgreSQL failed to start.
    popd
    exit /b 1
)

set "POSTGRES_HOST=127.0.0.1"
set "POSTGRES_PORT=5000"
set "POSTGRES_DB=postgres"
set "POSTGRES_USER=postgres"
set "POSTGRES_PASSWORD=postgres"
set "POSTGRES_SSL_MODE=disable"
set "SERVER_HOST=127.0.0.1"
set "SERVER_PORT=8989"
set "A365_RECORD_CONTENT=true"

echo.
echo Starting the API and agent locally at http://127.0.0.1:8989
echo PostgreSQL remains in Docker at 127.0.0.1:5000
echo Press Ctrl+C to stop the local API.
echo.

"%PYTHON%" main.py
set "EXIT_CODE=%ERRORLEVEL%"

popd
exit /b %EXIT_CODE%