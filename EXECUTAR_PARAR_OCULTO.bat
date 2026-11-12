@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0parar_agrosense.py"
) else (
    python "%~dp0parar_agrosense.py"
)
