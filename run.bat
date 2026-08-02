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

REM --- 4. API key -----------------------------------------------------------
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo   [!] A .env file has been created for you.
    echo.
    echo       Open .env and paste your API key after AI_API_KEY=  then run
    echo       this file again.
    echo.
    echo       Get a FREE Google Gemini key at https://aistudio.google.com/apikey
    echo       ^(the default settings use Gemini^). Other providers - Groq,
    echo       OpenRouter, a local Ollama model, OpenAI - are listed in .env.
    echo.
    notepad ".env"
    pause
    exit /b 0
)

REM Read AI_API_KEY out of .env. `eol=#` skips comment lines; splitting on "="
REM gives the key name in %%A and its value in %%B. Works with either Windows
REM or Unix line endings, unlike a findstr regex.
set "_HASKEY="
for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
    if /i "%%~A"=="AI_API_KEY" set "_HASKEY=%%~B"
)
if not defined _HASKEY (
    echo.
    echo   [!] AI_API_KEY is still empty in .env
    echo       Paste your key after the = sign, save, and run this file again.
    echo.
    notepad ".env"
    pause
    exit /b 0
)

echo   [3/4] Configuration looks good.
echo   [4/4] Starting the server...
echo.
echo   -------------------------------------------------------------
echo    IncidentIQ is starting at  http://127.0.0.1:8000
echo    Your browser will open automatically in a few seconds.
echo    Leave this window open. Close it, or press Ctrl+C, to stop.
echo   -------------------------------------------------------------
echo.

start "" /b cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8000"

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo   Server stopped.
pause
endlocal
