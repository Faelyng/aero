@echo off
REM Build Aero Mission Planner for Windows.
REM Run from the project root (e.g. from cmd.exe or PowerShell).
REM Requires Python 3.11+ and the venv set up on the Windows side:
REM   python -m venv .venv-win
REM   .venv-win\Scripts\pip install -r requirements.txt
REM   .venv-win\Scripts\pip install pyinstaller

setlocal
cd /d "%~dp0"

if exist ".venv-win\Scripts\pyinstaller.exe" (
    set PYINSTALLER=.venv-win\Scripts\pyinstaller.exe
) else if exist ".venv\Scripts\pyinstaller.exe" (
    set PYINSTALLER=.venv\Scripts\pyinstaller.exe
) else (
    set PYINSTALLER=pyinstaller
)

%PYINSTALLER% aero.spec --noconfirm
echo.
echo Build complete: dist\Aero Mission Planner\
