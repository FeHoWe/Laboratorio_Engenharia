@echo off
REM Inicia o NEXUS ENGINEERING LAB (cria o ambiente virtual na primeira execução)
cd /d "%~dp0"
if not exist .venv (
    py -3 -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)
python main\main.py %*
