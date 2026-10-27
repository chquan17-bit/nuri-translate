@echo off
chcp 65001 >nul
powershell.exe -NoProfile -STA -File "%~dp0scripts\Configure-Nuri.ps1"
if errorlevel 1 pause
