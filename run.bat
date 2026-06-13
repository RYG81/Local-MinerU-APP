@echo off
REM ============================================================
REM  MinerU-Local launcher - 100%% OFFLINE
REM  Starts TWO visible processes:
REM    1) mineru-api    (the parsing engine)  -> logs\api_*.log
REM    2) mineru-gradio (the web UI)          -> logs\ui_*.log
REM  Web UI:  http://127.0.0.1:7860
REM
REM  Why: letting the UI auto-spawn a hidden mineru-api subprocess is
REM  fragile on Windows (httpx.ReadError when that child dies). Running
REM  it ourselves makes it stable, restartable and properly logged.
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%~dp0"
set "PYEXE=%ROOT%python\python.exe"
set "API_PORT=8765"

if not exist "%PYEXE%" (
    echo Python environment not found. Run setup.bat first.
    pause
    exit /b 1
)

REM ---- Disable console QuickEdit (clicking console freezes server) ----
powershell -NoProfile -Command ^
  "$sig='[DllImport(\"kernel32.dll\")]public static extern IntPtr GetStdHandle(int n);[DllImport(\"kernel32.dll\")]public static extern bool SetConsoleMode(IntPtr h,int m);';" ^
  "$k=Add-Type -MemberDefinition $sig -Name K -PassThru;" ^
  "$h=$k::GetStdHandle(-10); $k::SetConsoleMode($h, 0x80) | Out-Null" 2>nul

REM ---- Offline + project-local environment ----
set "MINERU_TOOLS_CONFIG_JSON=%ROOT%mineru.json"
set "MINERU_MODEL_SOURCE=local"
set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"
set "MODELSCOPE_OFFLINE=1"
set "HF_HOME=%ROOT%hf-cache"
set "FTLANG_CACHE=%ROOT%models\fasttext"
set "HF_HUB_DISABLE_TELEMETRY=1"
set "GRADIO_ANALYTICS_ENABLED=False"
set "DO_NOT_TRACK=1"
set "NO_PROXY=localhost,127.0.0.1"
set "MINERU_LOG_LEVEL=INFO"
set "MINERU_MIN_BATCH_INFERENCE_SIZE=384"
REM One conversion at a time: prevents concurrent model loads, which on
REM Windows can exhaust the pagefile (os error 1455).
set "MINERU_API_MAX_CONCURRENT_REQUESTS=1"

"%PYEXE%" "%ROOT%scripts\make_config.py" || (pause & exit /b 1)

if not exist "%ROOT%logs" mkdir "%ROOT%logs"
for /f "tokens=* usebackq" %%t in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"`) do set "STAMP=%%t"
set "APILOG=%ROOT%logs\api_%STAMP%.log"
set "UILOG=%ROOT%logs\ui_%STAMP%.log"

echo.
echo  [1/2] Starting parsing engine (mineru-api) on port %API_PORT% ...
echo        log: %APILOG%
start "MinerU API engine" cmd /c ""%PYEXE%" -u -m mineru.cli.fast_api --host 127.0.0.1 --port %API_PORT% 2>&1 | "%PYEXE%" "%ROOT%scripts\tee.py" "%APILOG%""

echo        waiting for engine to come up (loads fast; models load on
echo        first request)...
"%PYEXE%" "%ROOT%scripts\wait_api.py" "http://127.0.0.1:%API_PORT%" 180 || (
    echo ENGINE FAILED TO START - see %APILOG%
    pause & exit /b 1
)

echo.
echo  [2/2] Starting web UI ...
echo        UI : http://127.0.0.1:7860   (opens automatically)
echo        log: %UILOG%
echo.
echo  First conversion loads models into the GPU: pipeline ~30s,
echo  vlm/hybrid a few minutes. Progress appears in the API window/log.
echo  To stop: close both console windows (or Ctrl+C in each).
echo.
start "" /b cmd /c "timeout /t 8 >nul & start http://127.0.0.1:7860"

"%PYEXE%" -u -m mineru.cli.gradio_app ^
    --server-name 127.0.0.1 ^
    --server-port 7860 ^
    --enable-example false ^
    --enable-api false ^
    --api-url http://127.0.0.1:%API_PORT% 2>&1 | "%PYEXE%" "%ROOT%scripts\tee.py" "%UILOG%"

echo.
echo UI stopped. Logs: %UILOG%  /  %APILOG%
echo (The API engine window may still be running - close it too.)
pause
