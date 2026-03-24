# Guida Completa all'Installazione (Macchina ATS Vergine)

Questa guida illustra la procedura passo-passo per installare l'intero applicativo **OCR Prescrizioni Cannabis** su un computer con sistema operativo Windows **totalmente vergine** (cioè privo di programmi pre-installati come Python, Docker o Ollama).

L'intero sistema è stato progettato per girare in un ambiente **Docker** isolato. In questo modo:
1. Non "sporca" il computer dell'operatore con innumerevoli pacchetti di programmazione.
2. Può essere rimosso completamente spegnendo i container e rimuovendo Docker Desktop.
3. Scarica in totale autonomia i pesanti modelli di intelligenza artificiale racchiudendoli nel docker.

---

## 🛠️ Fase 1: Installazione dei Prerequisiti Minimi
Poiché il computer è vergine, l'unica cosa che devi installare manualmente è **Git**. Questo ti permetterà di scaricare agilmente tutto il codice dal repository.

1. Scarica e installa **Git per Windows**: [https://gitforwindows.org/](https://gitforwindows.org/)
2. Durante l'installazione, puoi cliccare sempre *Avanti (Next)* lasciando tutte le opzioni di default.

---

## 📥 Fase 2: Download dell'Applicativo
Ora che hai Git, scarica il progetto:

1. Apri il **Prompt dei Comandi (`cmd`)** dal menu Start.
2. Spostati nella cartella in cui vuoi salvare l'applicativo (es. il Desktop):
   ```cmd
   cd %USERPROFILE%\Desktop
   ```
3. Clona il repository:
   ```cmd
   git clone https://github.com/Degioo/ocrlocale.git
   ```
4. Entra nella cartella appena scaricata:
   ```cmd
   cd ocrlocale
   ```

---

## ⚙️ Fase 3: Prima Passata (Installazione Docker)
Ora utilizzeremo lo script automatico che si occuperà di predisporre Docker.

1. Sempre dal `cmd`, esegui:
   ```cmd
   Installa_Macchina_Vergine_Docker.bat
   ```
2. Lo script rileverà che **Docker Desktop** non è presente e lo installerà automaticamente utilizzando `winget` (potrebbe comparire una richiesta di approvazione).
3. **IMPORTANTE**: L'installazione di Docker su Windows abilita la virtualizzazione WSL2 e **richiede quasi sempre il riavvio del PC**.

### 👉 Azioni dopo il Riavvio:
- Riavvia il computer.
- Apri **Docker Desktop** dal menu Start. La primissima volta ti farà accettare i termini di servizio (*Accept the License Agreement*).
- Aspetta che l'icona della "balena" in basso a destra (nella tray, vicino all'orologio) sia in stato di avvio completato *(Engine Running)*.

---

## 🚀 Fase 4: Seconda Passata (Compilazione, Download LLM e Avvio)
1. Riapri il **Prompt dei Comandi (`cmd`)**.
2. Torna nella cartella creata prima:
   ```cmd
   cd %USERPROFILE%\Desktop\ocrlocale
   ```
3. Rilancia nuovamente lo stesso script:
   ```cmd
   Installa_Macchina_Vergine_Docker.bat
   ```
   Questa volta lo script capirà che Docker è presente e farà tutto il resto magicamente:
   - Scaricherà le immagini, costruirà i container e compilerà l'app in un ambiente isolato.
   - Avvierà un container secondario per **Ollama**.
   - **Scaricherà il modello LLM (`llama3.2`)** necessario per il parsing delle ricette (l'operazione impiegherà qualche minuto in background).
   - Genererà automaticamente l'icona di collegamento **"OCR Cannabis (Docker)"** sul Desktop.

---

## 🎯 Fase 5: Utilizzo Quotidiano (Per l'Operatore)
L'installazione è terminata. Da adesso in poi tu e l'operatore ATS **non dovrete mai più usare il `cmd`**.

Per avviare il software in qualsiasi momento basterà:
1. Assicurarsi di aver aperto Docker Desktop.
2. Fare **doppio clic** sull'icona **"OCR Cannabis (Docker)"** presente sul Desktop.

*(Dietro le quinte, il collegamento lancerà lo script `Avvia_Docker.bat` passandogli tutto in modo pulito).*

---

### 📁 Cartelle di Lavoro (Input / Output)
L'integrazione di Docker prevede che le cartelle locali e quelle nel container siano mappate. I documenti andranno posizionati nelle cartelle create assieme al codice:
- **`input/`** (e la sottocartella \`pdf\` all'interno se prevista)
- **`output/`** (da cui prelevare i risultati)
