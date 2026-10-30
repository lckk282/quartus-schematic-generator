@echo off
title Quartus Placer
cd /d "%~dp0"
chcp 65001 >nul
where python >nul 2>nul
if errorlevel 1 goto nopython
python "%~dp0launcher.py"
if errorlevel 1 pause
exit /b 0

:nopython
echo.
echo   [!] Python not found. Please run the setup file (install.bat) first.
echo.
pause
exit /b 1
