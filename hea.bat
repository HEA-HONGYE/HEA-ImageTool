@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
echo Missing virtual environment: .venv
    echo Please run: py -m venv .venv
    echo Then run: .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)

"%PYTHON%" -m image_toolbox
