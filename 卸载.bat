@echo off
title Quartus Placer - Uninstall
cd /d "%~dp0"
chcp 65001 >nul
where python >nul 2>nul
if errorlevel 1 goto nopython
python "%~dp0uninstall.py" %*
exit /b 0

:nopython
echo.
echo   [!] Python not found.
echo.
pause
exit /b 1
