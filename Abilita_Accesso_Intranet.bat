@echo off
title Configurazione Firewall OCR Cannabis
echo ========================================================
echo       Apertura Porta 8501 per Accesso Intranet ATS
echo ========================================================
echo.

:: Controllo privilegi di amministratore
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :admin
) else (
    echo E' necessario eseguire questo script come Amministratore.
    echo Richiesta permessi in corso...
    powershell -Command "Start-Process -FilePath '%0' -Verb RunAs"
    exit /b
)

:admin
echo Permessi acquisiti. Configurazione del Firewall di Windows...
echo.

:: Rimuovi regola esistente per evitare duplicati nel caso venga eseguito più volte
powershell -Command "Remove-NetFirewallRule -DisplayName 'OCR Cannabis App' -ErrorAction SilentlyContinue"

:: Aggiungi la nuova regola per la porta 8501
powershell -Command "New-NetFirewallRule -DisplayName 'OCR Cannabis App' -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow -Profile Domain,Private,Public"

echo.
if %errorLevel% == 0 (
    echo [SUCCESSO] Regola Firewall aggiunta!
    echo Ora l'applicazione OCR Cannabis e' accessibile dagli altri PC ATS.
    echo.
    echo Per connettersi, utilizzare l'indirizzo IP di questa macchina
    echo seguito dalla porta :8501 (esempio: http://192.168.1.10:8501)
) else (
    echo [ERRORE] Si e' verificato un problema durante la configurazione del firewall.
)
echo.
pause
