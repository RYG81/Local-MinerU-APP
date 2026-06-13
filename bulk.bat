@echo off
REM ============================================================
REM  MinerU-Local BULK conversion - 100%% offline
REM  Drag & drop a folder onto this file, or run:
REM     bulk.bat C:\path\to\folder [pipeline|vlm-engine|hybrid-engine]
REM  Output: output\bulk\<timestamp>\ + one ZIP with md/json/images
REM  Log:    logs\bulk_<timestamp>.log
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"
set "PYEXE=%~dp0python\python.exe"

if not exist "%PYEXE%" (
    echo Python environment not found. Run setup.bat first.
    pause & exit /b 1
)
if "%~1"=="" (
    echo Usage: bulk.bat ^<folder-or-file^> [backend]
    echo   backend: pipeline (default, fastest) ^| vlm-engine ^| hybrid-engine
    pause & exit /b 1
)

set "BACKEND=%~2"
if "%BACKEND%"=="" set "BACKEND=pipeline"

"%PYEXE%" "%~dp0scripts\bulk_convert.py" "%~1" -b %BACKEND%
pause
