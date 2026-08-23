@echo off
setlocal
set "TRACKSCRIBE_ROOT=%~dp0"

echo TrackScribe Setup
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TRACKSCRIBE_ROOT%scripts\bootstrap.ps1" %*
set "TRACKSCRIBE_EXIT=%ERRORLEVEL%"
echo.
if not "%TRACKSCRIBE_EXIT%"=="0" (
    echo TrackScribe setup did not complete. Review the error above.
)
if /I "%TRACKSCRIBE_NO_PAUSE%"=="1" goto :exit
echo Press any key to close...
pause >nul
:exit
exit /b %TRACKSCRIBE_EXIT%
