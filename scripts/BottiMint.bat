@echo off
chcp 65001 >nul
title BottiMint
rem Abre la interfaz grafica pidiendo administrador (requiere Python). Para usar sin Python: BottiMint.exe
>nul 2>&1 net session
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
cd /d "%~dp0.."
set PY=
where py >nul 2>&1 && set PY=py -3
if not defined PY where python >nul 2>&1 && set PY=python
if not defined PY (
  echo No se encontro Python. Instalalo desde https://www.python.org/downloads/ ^(marcando "Add python.exe to PATH"^)
  echo o usa BottiMint.exe de la seccion Releases de GitHub.
  pause & exit /b
)
if "%~1"=="" (
  %PY% -m bottimint
) else (
  %PY% -m bottimint %*
  pause
)
