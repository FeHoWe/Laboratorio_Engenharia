@echo off
REM Gera dist\NEXUS\NEXUS.exe com PyInstaller. AVISO: este empacotamento NÃO foi testado em Windows (V3.6).
REM Depois de gerar, rode dist\NEXUS\NEXUS.exe e tools\verificar_windows.bat e envie o resultado. OpenFOAM/CalculiX NÃO vão dentro do pacote:
REM CalculiX deve estar no PATH; OpenFOAM roda via WSL2 (veja NEXUS_INSTALLATION.md).
cd /d "%~dp0\.."
if not exist .venv ( py -3 -m venv .venv )
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm nexus.spec
if errorlevel 1 ( echo FALHOU o empacotamento & exit /b 1 )
echo OK: dist\NEXUS\NEXUS.exe  (teste agora; se faltar módulo, adicione em hidden no nexus.spec)
