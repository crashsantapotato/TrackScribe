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
echo Press any key to close...
pause >nul
exit /b %TRACKSCRIBE_EXIT%
