@echo off
echo Avvio Interfaccia OCR Prescrizioni Cannabis...

:: Prova ad avviare Ollama in background (se e' gia' avviato, la finestra si chiudera' da sola)
start "Ollama Server" /min ollama serve

cd /d "%~dp0"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: Avvia l'interfaccia grafica
start "" pythonw gui.py
