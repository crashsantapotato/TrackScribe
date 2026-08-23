@echo off
setlocal
set "TRACKSCRIBE_ROOT=%~dp0"
set "TRACKSCRIBE_UI_PYTHON=%TRACKSCRIBE_ROOT%.venv-ui\Scripts\pythonw.exe"

if not exist "%TRACKSCRIBE_UI_PYTHON%" (
    echo TrackScribe is not set up yet.
    echo.
    echo Run setup.bat first.
    echo.
    echo Press any key...
    pause >nul
    exit /b 1
)

cd /d "%TRACKSCRIBE_ROOT%"
start "" "%TRACKSCRIBE_UI_PYTHON%" "%TRACKSCRIBE_ROOT%ui.py"
exit /b 0
