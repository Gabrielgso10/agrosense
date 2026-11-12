@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0iniciar_agrosense.py"
) else (
    python "%~dp0iniciar_agrosense.py"
)
