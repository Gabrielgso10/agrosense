@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Ponte AgroSense: 3 bombas Wokwi para painel local ===
py bridge_wokwi_3bombas.py
if errorlevel 1 (
  echo Ocorreu um erro. Verifique o Python e a instalacao do paho-mqtt.
  pause
)
