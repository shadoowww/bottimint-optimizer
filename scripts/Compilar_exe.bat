@echo off
chcp 65001 >nul
cd /d "%~dp0.."
where py >nul 2>&1 && (set PY=py -3) || (set PY=python)
%PY% -m pip install -r requirements-dev.txt
%PY% -m PyInstaller --onefile --noconsole --uac-admin --name BottiMint run.py
echo.
echo Listo: dist\BottiMint.exe
pause
