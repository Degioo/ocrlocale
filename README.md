# OCR Prescrizioni Cannabis

Applicazione per l'estrazione e il controllo automatizzato dei dati dalle prescrizioni di cannabis medica, basato su tecniche di OCR e LLM (tramite Ollama) con il confronto finale su file Excel.

## Prerequisiti
- **Sistema Operativo:** Windows 10 / 11.
- **Python:** Versione 3.12 (o superiore) installato e presente nelle variabili d'ambiente (PATH).
- **Ollama:** Installato localmente ed in esecuzione in background per utilizzare l'LLM impostato nel file `llm_config_local.json`.

## Installazione per Uso Locale (Macchina ATS)
Per installare automaticamente tutte le dipendenze e creare l'ambiente virtuale sulla macchina di destinazione:

1. Eseguire (doppio clic) il file **`Installa_ATS.bat`**.
2. Lo script effettuerà automaticamente le seguenti operazioni:
   - Controllo e creazione dell'ambiente virtuale Python (`venv`).
   - Installazione dei pacchetti Python necessari (elencati in `requirements.txt`).
   - Creazione di un comodo collegamento chiamato **"OCR Cannabis"** sul Desktop dell'utente.

## Installazione con Docker (Opzione Consigliata per non lasciare tracce)
Se preferisci mantenere il sistema pulito e poter disinstallare tutto facilmente:
1. Assicurati di avere **Docker Desktop** installato (con integrazione WSL2 abilitata per il supporto grafico della GUI su Windows).
2. Fai doppio clic su **`Avvia_Docker.bat`** per scaricare, costruire e lanciare un container isolato.
3. Per rimuovere l'applicazione, basterà eliminare l'immagine da Docker Desktop o lanciare `docker-compose down --rmi all`.

## Struttura e Cartelle Importanti
- **`input/`**: Contiene il file Excel di riferimento e la sottocartella \`pdf\` in cui inserire le prescrizioni scansionate da elaborare.
- **`output/`**: Cartella auto-generata dal programma al termine dell'elaborazione, in cui vengono salvati i risultati (file Excel confrontato, eventuale resoconto anomalie e i PDF convertiti in un formato ottimizzato per i layout ATS).
