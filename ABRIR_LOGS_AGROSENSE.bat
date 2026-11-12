@echo off
set "LOGS=%LOCALAPPDATA%\AgroSense\logs"
if exist "%LOGS%" (
  start "" explorer.exe "%LOGS%"
) else (
  echo Logs nao foram criados ainda.
  pause
)
