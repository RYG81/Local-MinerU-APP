@echo off
REM ============================================================
REM  One-time fix for UI problems (Convert does nothing /
REM  Advanced options hidden): pins Gradio to the stable 5.x
REM  line that MinerU's UI was built against. Needs internet.
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"
set "PYEXE=%~dp0python\python.exe"
if not exist "%PYEXE%" (
    echo Python environment not found. Run setup.bat first.
    pause & exit /b 1
)
echo Current Gradio version:
"%PYEXE%" -c "import gradio; print(gradio.__version__)"
echo.
echo Installing Gradio 5.49.1 (stable line for MinerU's UI)...
"%PYEXE%" -m pip install --no-warn-script-location "gradio==5.49.1" "gradio-pdf>=0.0.22" || (
    echo Install failed - check your internet connection.
    pause & exit /b 1
)
echo.
echo Done. Start the app again with run.bat
pause
