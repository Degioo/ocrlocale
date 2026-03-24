@echo off
setlocal
echo ========================================================
echo        Installazione OCR Prescrizioni Cannabis
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/3] Controllo esistenza ambiente virtuale (venv)...
if not exist "venv\Scripts\python.exe" (
    echo Creazione ambiente virtuale in corso...
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERRORE] Impossibile creare il venv. Verifica che Python sia installato e nel PATH.
        pause
        exit /b 1
    )
) else (
    echo Ambiente virtuale gia' presente.
)

echo.
echo [2/3] Installazione delle dipendenze...
call venv\Scripts\activate.bat
python.exe -m pip install --upgrade pip
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERRORE] Errore durante l'installazione delle dipendenze. Controllare i messaggi sopra.
    pause
    exit /b 1
)

echo.
echo [3/3] Creazione del collegamento sul Desktop...
set VBS_SCRIPT="%TEMP%\CreaCollegamentoOCR_ATS.vbs"
set SHORTCUT_PATH="%USERPROFILE%\Desktop\OCR Cannabis.lnk"

:: Generazione script VBS per la creazione del collegamento
echo Set oWS = WScript.CreateObject("WScript.Shell") > %VBS_SCRIPT%
echo sLinkFile = %SHORTCUT_PATH% >> %VBS_SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %VBS_SCRIPT%
echo oLink.TargetPath = "%~dp0Avvia_OCR_Cannabis.bat" >> %VBS_SCRIPT%
echo oLink.WorkingDirectory = "%~dp0" >> %VBS_SCRIPT%
echo oLink.Description = "Avvia Applicativo OCR Prescrizioni Cannabis" >> %VBS_SCRIPT%
echo oLink.Save >> %VBS_SCRIPT%

:: Esecuzione script VBS e pulizia
cscript //nologo %VBS_SCRIPT%
del %VBS_SCRIPT%

echo.
echo ========================================================
echo        Installazione Completata con Successo!
echo ========================================================
echo.
echo E' stato creato un collegamento chiamato "OCR Cannabis" sul Desktop.
echo Una volta chiuso questo programma, puoi avviare l'applicazione dal Desktop.
echo.
pause
