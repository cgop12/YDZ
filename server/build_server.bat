@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ========================================
echo TypeBattle Server - Build Script
echo ========================================
echo.

if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"

py -m pip install pyinstaller websockets PyQt6 psutil -q 2>nul

py -m PyInstaller TypeBattleServer.spec --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build complete: dist\TypeBattleServer.exe
echo ========================================
pause
