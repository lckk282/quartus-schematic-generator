@echo off
title Quartus Placer - Setup
cd /d "%~dp0"
chcp 65001 >nul
where python >nul 2>nul
if errorlevel 1 goto nopython
python "%~dp0install.py" %*
if errorlevel 1 pause
exit /b 0

:nopython
echo.
echo   [!] Python not found on this computer.
echo.
echo   Install Python 3.8+ from:  https://www.python.org/downloads/
echo   IMPORTANT: on the first page check "Add python.exe to PATH".
echo.
echo   Then double-click this file again.
echo.
pause
exit /b 1
