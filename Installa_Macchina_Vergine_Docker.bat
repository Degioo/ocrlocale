@echo off
setlocal
echo ========================================================
echo   Installazione COMPLETA OCR Prescrizioni Cannabis (Docker)
echo ========================================================
echo.
echo Questo script installera' automaticamente:
echo 1) Docker Desktop (se assente) tramite Winget
echo 2) I container dell'applicazione OCR e Ollama
echo 3) Il modello LLM (llama3.2)
echo 4) Il collegamento sul Desktop
echo.
echo ATTENZIONE: Potrebbero essere richiesti i permessi di 
echo amministratore e forse un Riavvio del PC per Docker.
echo.
pause

echo.
echo [1/4] Controllo ed Installazione Docker Desktop...
docker --version >nul 2>&1
if %ERRORLEVEL% EQU 0 goto docker_ready

echo Docker non trovato! Avvio installazione tramite Winget...
winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
if %ERRORLEVEL% NEQ 0 (
    echo [ERRORE] Installazione Docker fallita. Installa Docker Desktop manualmente da docker.com.
    pause
    exit /b 1
)
echo.
echo [ATTENZIONE] Docker e' stato installato.
echo Potrebbe essere necessario RIAVVIARE il PC.
echo Dopo il riavvio o l'apertura manuale di Docker Desktop (icona tray azzurra),
echo rilancia questo stesso file per continuare l'installazione.
echo.
pause
exit /b 0

:docker_ready
echo Docker e' installato! Procedo con la build...

echo.
echo [2/4] Build e Avvio dei Container (OCR + Ollama)...
cd /d "%~dp0"
docker compose up -d --build
if %ERRORLEVEL% NEQ 0 (
    echo [ERRORE] Impossibile avviare i container.
    echo ----------------------------------------------------
    echo HAI APERTO DOCKER DESKTOP?
    echo Cerca "Docker Desktop" nel menu Start di Windows e aprilo.
    echo Assicurati che l'icona in basso a destra sia verde.
    echo Poi riavvia questo script.
    echo ----------------------------------------------------
    pause
    exit /b 1
)

echo.
echo [3/4] Scaricamento del modello LLM (llama3.2)...
echo Questa operazione puo' richiedere alcuni minuti a seconda della connessione internet.
docker exec ocr_ollama ollama run llama3.2 "Sei pronto?" >nul 2>&1
echo Modello pronto!

echo.
echo [4/4] Creazione del collegamento sul Desktop...
set VBS_SCRIPT="%TEMP%\CreaCollegamentoOCR_Vergine.vbs"
set SHORTCUT_PATH="%USERPROFILE%\Desktop\OCR Cannabis (Docker).lnk"

echo Set oWS = WScript.CreateObject("WScript.Shell") > %VBS_SCRIPT%
echo sLinkFile = %SHORTCUT_PATH% >> %VBS_SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %VBS_SCRIPT%
echo oLink.TargetPath = "%~dp0Avvia_Docker.bat" >> %VBS_SCRIPT%
echo oLink.WorkingDirectory = "%~dp0" >> %VBS_SCRIPT%
echo oLink.Description = "Avvia Applicativo OCR Prescrizioni Cannabis tramite Docker" >> %VBS_SCRIPT%
echo oLink.Save >> %VBS_SCRIPT%

cscript //nologo %VBS_SCRIPT%
del %VBS_SCRIPT%

echo.
echo ========================================================
echo        Installazione Completata con Successo!
echo ========================================================
echo E' stato creato un collegamento "OCR Cannabis (Docker)" sul Desktop.
echo Una volta chiuso questo programma, puoi avviare l'applicazione cliccando il collegamento.
echo Tutto e' confinato in Docker e removibile facilmente cancellando i container!
echo.
pause
