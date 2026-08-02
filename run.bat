@echo off
REM ===========================================================================
REM  IncidentIQ - one-click launcher for Windows.
REM
REM  Double-click this file. It sets up everything on first run and opens the
REM  app in your browser. Nothing needs to be installed except Python.
REM ===========================================================================

setlocal
cd /d "%~dp0"

echo.
echo   IncidentIQ
echo   ==========
echo.

REM --- 1. Python present? ---------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo   [X] Python was not found on this computer.
    echo.
    echo       Install Python 3.10 or newer from https://www.python.org/downloads/
    echo       During installation, tick "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

REM --- 2. Virtual environment ----------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo   [1/4] Creating a virtual environment ^(first run only^)...
    python -m venv .venv
    if errorlevel 1 (
        echo   [X] Could not create the virtual environment.
        pause
        exit /b 1
    )
) else (
    echo   [1/4] Virtual environment found.
)

REM --- 3. Dependencies ------------------------------------------------------
echo   [2/4] Installing dependencies ^(this may take a minute the first time^)...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo   [X] Installing dependencies failed. Check your internet connection.
    pause
    exit /b 1
)

REM --- 4. Local configuration ----------------------------------------------
if not exist ".env" (
    copy ".env.example" ".env" >nul
)

echo   [3/4] Local configuration ready.

REM --- 5. Refuse to open an older server on the same port ------------------
".venv\Scripts\python.exe" -m app.portcheck --host 127.0.0.1 --port 8000
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

echo   [4/4] Starting the server...
echo.
echo   -------------------------------------------------------------
echo    IncidentIQ is starting at  http://127.0.0.1:8000
echo    Your browser will open automatically in a few seconds.
echo    Leave this window open. Close it, or press Ctrl+C, to stop.
echo   -------------------------------------------------------------
echo.

start "" /b cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8000/?commit=12"

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo   Server stopped.
pause
endlocal
