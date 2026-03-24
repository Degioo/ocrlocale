@echo off
echo ========================================================
echo        Avvio OCR Prescrizioni Cannabis via Docker
echo ========================================================
echo.
echo Per usare questa opzione e' necessario avere Docker Desktop 
echo in esecuzione e configurato per supportare WSL2/WSLg (per la grafica).
echo.

cd /d "%~dp0"
docker-compose up --build

pause
