@echo off
cd /d "%~dp0"
if not exist "%~dp0INICIAR_AGROSENSE_OCULTO.vbs" (
  echo Falta o arquivo INICIAR_AGROSENSE_OCULTO.vbs na pasta do AgroSense.
  pause
  exit /b 1
)
wscript.exe "%~dp0INICIAR_AGROSENSE_OCULTO.vbs"
exit /b 0
