@echo off
REM ============================================================
REM  MinerU-Local BULK conversion - 100%% offline
REM  Drag & drop a folder onto this file, or run:
REM     bulk.bat C:\path\to\folder [backend] [ocr-language]
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
    echo Usage: bulk.bat ^<folder-or-file^> [backend] [ocr-language]
    echo   backend: pipeline (default, fastest) ^| vlm-engine ^| hybrid-engine
    echo   OCR language: en (default) ^| devanagari for Hindi ^| ...
    pause & exit /b 1
)

set "BACKEND=%~2"
if "%BACKEND%"=="" set "BACKEND=pipeline"
set "LANG=%~3"
if "%LANG%"=="" set "LANG=en"

"%PYEXE%" "%~dp0scripts\bulk_convert.py" "%~1" -b %BACKEND% --lang %LANG%
pause
