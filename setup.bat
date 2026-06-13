@echo off
REM ============================================================
REM  MinerU-Local one-time setup (requires internet ONCE)
REM  Installs a private embedded Python + all packages + models
REM  entirely INSIDE this folder. After this, run.bat is offline.
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%~dp0"
set "PYDIR=%ROOT%python"
set "PYEXE=%PYDIR%\python.exe"
set "PYVER=3.12.10"
set "PYZIP=python-%PYVER%-embed-amd64.zip"

REM --ssl-no-revoke: Windows curl uses Schannel, which fails on networks
REM where cert revocation checks are blocked (corporate proxy/AV).
REM Certificate validation itself is still performed.
set "CURL=curl -L --ssl-no-revoke --retry 3 --retry-delay 2"

REM Keep ALL caches inside the project folder
set "HF_HOME=%ROOT%hf-cache"
set "PIP_CACHE_DIR=%ROOT%pip-cache"
set "FTLANG_CACHE=%ROOT%models\fasttext"
set "HF_HUB_DISABLE_TELEMETRY=1"
set "GRADIO_ANALYTICS_ENABLED=False"
set "DO_NOT_TRACK=1"
REM Make sure a previously-set 'local' source doesn't block downloads
set "MINERU_MODEL_SOURCE=huggingface"
set "HF_HUB_OFFLINE="
set "TRANSFORMERS_OFFLINE="

echo.
echo ============================================================
echo  [0/6] Pre-flight checks
echo ============================================================
where nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo WARNING: nvidia-smi not found. Install/update the NVIDIA driver
    echo          ^(R570 or newer required for RTX 50-series / CUDA 12.8^).
) else (
    nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
)
if not exist "%SystemRoot%\System32\vcruntime140.dll" (
    echo WARNING: MSVC runtime missing. Install "Microsoft Visual C++
    echo          2015-2022 Redistributable x64" before using run.bat:
    echo          https://aka.ms/vs/17/release/vc_redist.x64.exe
)

echo.
echo ============================================================
echo  [1/6] Private Python %PYVER% (embedded, portable)
echo ============================================================
if exist "%PYEXE%" (
    echo Already present - skipping.
) else (
    echo Downloading Python embeddable package...
    %CURL% -o "%PYZIP%" "https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip"
    if errorlevel 1 (
        echo curl failed, trying PowerShell download instead...
        powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip' -OutFile '%PYZIP%'" || goto :fail
    )
    mkdir "%PYDIR%" 2>nul
    tar -xf "%PYZIP%" -C "%PYDIR%" || goto :fail
    del "%PYZIP%"
    REM Enable site-packages in the embedded distribution
    powershell -NoProfile -Command "(Get-Content '%PYDIR%\python312._pth') -replace '#import site','import site' | Set-Content '%PYDIR%\python312._pth'" || goto :fail
)

echo.
echo ============================================================
echo  [2/6] pip
echo ============================================================
"%PYEXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
    %CURL% -o get-pip.py https://bootstrap.pypa.io/get-pip.py
    if errorlevel 1 (
        echo curl failed, trying PowerShell download instead...
        powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'" || goto :fail
    )
    "%PYEXE%" get-pip.py --no-warn-script-location || goto :fail
    del get-pip.py
) else (
    echo Already present - skipping.
)

echo.
echo ============================================================
echo  [3/6] PyTorch with CUDA 12.8 (required for RTX 50-series)
echo ============================================================
"%PYEXE%" -m pip install --no-warn-script-location "torch<3" torchvision --index-url https://download.pytorch.org/whl/cu128 || goto :fail

echo.
echo ============================================================
echo  [4/6] MinerU (core: pipeline + VLM + Gradio UI)
echo ============================================================
REM Pinned version = reproducible install. The HF Space runs this same
REM package. Bump deliberately if you ever want to upgrade.
"%PYEXE%" -m pip install --no-warn-script-location "mineru[core]==3.3.1" || goto :fail

REM Pin Gradio to the stable 5.x line: MinerU's UI has known issues on
REM Gradio 6 (Convert events stuck in 'processing', advanced-options
REM popover not opening) which its own source code works around only
REM partially. 5.49.x is what the HF Space experience is based on.
"%PYEXE%" -m pip install --no-warn-script-location "gradio==5.49.1" "gradio-pdf>=0.0.22" || goto :fail

echo.
echo Verifying all critical imports work (catches missing DLLs now,
echo while we still have internet, instead of failing later offline)...
"%PYEXE%" -c "import torch, torchvision, transformers, accelerate, gradio, gradio_pdf, cv2, onnxruntime, mineru; print('imports OK')" || goto :fail

echo.
echo ============================================================
echo  [5/6] Downloading models into .\models\  (several GB)
echo ============================================================
"%PYEXE%" "%ROOT%scripts\download_models.py" || goto :fail

echo.
echo ============================================================
echo  [6/6] Verifying installation
echo ============================================================
"%PYEXE%" "%ROOT%scripts\check_setup.py" || goto :fail

echo.
echo ============================================================
echo  [7/7] OFFLINE smoke test: parse a real PDF with BOTH
echo        backends using local models only (proves the whole
echo        chain works on THIS machine before you go offline).
echo        First VLM run loads the model - allow a few minutes.
echo ============================================================
"%PYEXE%" "%ROOT%scripts\smoke_test.py" || goto :fail

echo.
echo ============================================================
echo  Setup complete and SMOKE-TESTED!
echo  Use run.bat to start the app (offline).
echo  You may delete the pip-cache folder to save disk space.
echo ============================================================
pause
exit /b 0

:fail
echo.
echo ************  SETUP FAILED - see error above  ************
echo.
echo Common causes on corporate/locked-down networks:
echo  - SSL inspection breaking downloads: if pip fails with SSL errors,
echo    re-run setup on another network or hotspot, OR add your company
echo    root certificate to pip:  set PIP_CERT=path\to\corp-root.pem
echo  - Proxy required: set HTTPS_PROXY=http://user:pass@proxy:port
echo    before running setup.bat
pause
exit /b 1
