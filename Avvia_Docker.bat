@echo off
echo ========================================================
echo        Avvio OCR Prescrizioni Cannabis (Web App)
echo ========================================================
echo.
echo Avvio in corso dei container Docker...

cd /d "%~dp0"
docker compose up -d

echo.
echo Apre il browser alla pagina locale: http://localhost:8501
echo Attendi qualche secondo che il caricamento finisca...
timeout /t 3 /nobreak >nul
start http://localhost:8501

pause
