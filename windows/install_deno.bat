@echo off
TITLE Install Deno for YouTube Signature Solving
CLS

echo ==================================================
echo      Installing Deno JavaScript Runtime
echo ==================================================
echo.
echo Deno is required for YouTube signature solving.
echo This will install Deno system-wide (not in venv).
echo.

REM Check if Deno is already installed
where.exe deno >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Deno is already installed!
    deno --version
    echo.
    echo Deno is ready to use with yt-dlp.
    pause
    exit
)

echo [INFO] Installing Deno using PowerShell...
echo.

REM Install Deno using PowerShell (Windows)
powershell -Command "irm https://deno.land/install.ps1 | iex"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install Deno automatically.
    echo.
    echo Please install Deno manually:
    echo   1. Visit: https://docs.deno.com/runtime/getting_started/installation/
    echo   2. Download and install Deno
    echo   3. Make sure Deno is added to your PATH
    echo.
    echo Or use: powershell -Command "irm https://deno.land/install.ps1 | iex"
    echo.
    pause
    exit
)

echo.
echo [INFO] Adding Deno to PATH for current session...
set "PATH=%USERPROFILE%\.deno\bin;%PATH%"

echo.
echo [INFO] Verifying installation...
where.exe deno >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Deno installed successfully!
    deno --version
    echo.
    echo IMPORTANT: You may need to restart your terminal or add Deno to PATH permanently.
    echo Deno is typically installed to: %USERPROFILE%\.deno\bin
    echo.
    echo To add Deno to PATH permanently:
    echo   1. Open System Properties ^> Environment Variables
    echo   2. Add %USERPROFILE%\.deno\bin to your User PATH
    echo   3. Restart your terminal
    echo.
) else (
    echo [WARNING] Deno was installed but not found in PATH.
    echo You may need to restart your terminal or add it manually.
    echo.
    echo Deno should be at: %USERPROFILE%\.deno\bin\deno.exe
    echo.
)

echo ==================================================
echo           Deno Installation Complete!
echo ==================================================
echo.
echo Next steps:
echo   1. Restart your terminal (or run: refreshenv)
echo   2. Verify: deno --version
echo   3. Run your music downloader - it will use Deno automatically
echo.
pause
