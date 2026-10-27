@echo off
chcp 65001 >nul
powershell.exe -NoProfile -File "%~dp0scripts\Start-Nuri.ps1" -Mode register
pause
