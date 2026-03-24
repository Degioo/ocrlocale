import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import json
import queue
from pathlib import Path

from app.core.pipeline import PipelineRunner

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("OCR Prescrizioni Cannabis")
        self.geometry("1100x700")
        
        # Grid layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.msg_queue = queue.Queue()
        self.pipeline_thread = None

        # Load Settings initially
        self.llm_cfg_path = Path("llm_config_local.json")
        self.load_settings()

        self._build_sidebar()
        self._build_frames()
        
        self.show_elaborazione()

        # Queue checker
        self.after(100, self.process_queue)

    def load_settings(self):
        if self.llm_cfg_path.exists():
            with open(self.llm_cfg_path, 'r') as f:
                self.llm_config = json.load(f)
        else:
            self.llm_config = {"base_url": "http://localhost:11434/v1", "model": "llama3.2"}
        self.use_vision = False

    def save_settings(self):
        self.llm_config["model"] = self.entry_model.get()
        self.use_vision = self.pipeline_switch.get() == 1
        with open(self.llm_cfg_path, 'w') as f:
            json.dump(self.llm_config, f, indent=4)
        messagebox.showinfo("Successo", "Impostazioni salvate!")

    def _build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="OCR Cannabis", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 30))

        self.btn_elaborazione = ctk.CTkButton(self.sidebar_frame, text="Elaborazione", command=self.show_elaborazione)
        self.btn_elaborazione.grid(row=1, column=0, padx=20, pady=10)

        self.btn_monitoraggio = ctk.CTkButton(self.sidebar_frame, text="Monitoraggio Dati", command=self.show_monitoraggio)
        self.btn_monitoraggio.grid(row=2, column=0, padx=20, pady=10)

        self.btn_impostazioni = ctk.CTkButton(self.sidebar_frame, text="Impostazioni", command=self.show_impostazioni)
        self.btn_impostazioni.grid(row=3, column=0, padx=20, pady=10)

        self.btn_log = ctk.CTkButton(self.sidebar_frame, text="Log di Sistema", command=self.show_log)
        self.btn_log.grid(row=4, column=0, padx=20, pady=10)

        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Tema:", anchor="w")
        self.appearance_mode_label.grid(row=6, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Light", "Dark", "System"],
                                                               command=lambda mode: ctk.set_appearance_mode(mode))
        self.appearance_mode_optionemenu.grid(row=7, column=0, padx=20, pady=(10, 20))

    def _build_frames(self):
        self.frames = {}
        
        self.frame_elaborazione = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_elaborazione.grid_columnconfigure(0, weight=1)
        self.setup_elaborazione()
        self.frames["Elaborazione"] = self.frame_elaborazione

        self.frame_monitoraggio = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_monitoraggio.grid_columnconfigure(0, weight=1)
        self.frame_monitoraggio.grid_rowconfigure(2, weight=1)
        self.setup_monitoraggio()
        self.frames["Monitoraggio"] = self.frame_monitoraggio

        self.frame_impostazioni = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_impostazioni.grid_columnconfigure(0, weight=1)
        self.setup_impostazioni()
        self.frames["Impostazioni"] = self.frame_impostazioni

        self.frame_log = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_log.grid_columnconfigure(0, weight=1)
        self.frame_log.grid_rowconfigure(1, weight=1)
        self.setup_log()
        self.frames["Log"] = self.frame_log

    def setup_elaborazione(self):
        lbl = ctk.CTkLabel(self.frame_elaborazione, text="Dashboard Elaborazione", font=ctk.CTkFont(size=24, weight="bold"))
        lbl.grid(row=0, column=0, padx=30, pady=(30, 20), sticky="w")
        
        dir_frame = ctk.CTkFrame(self.frame_elaborazione)
        dir_frame.grid(row=1, column=0, padx=30, pady=10, sticky="ew")
        dir_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(dir_frame, text="Cartella Input (PDF):").grid(row=0, column=0, padx=20, pady=10, sticky="e")
        self.entry_input = ctk.CTkEntry(dir_frame)
        self.entry_input.insert(0, os.path.abspath("input"))
        self.entry_input.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="ew")
        ctk.CTkButton(dir_frame, text="Sfoglia...", command=self.browse_input).grid(row=0, column=2, padx=20, pady=10)
        
        ctk.CTkLabel(dir_frame, text="File Excel Regionale:").grid(row=1, column=0, padx=20, pady=10, sticky="e")
        self.entry_excel = ctk.CTkEntry(dir_frame, placeholder_text="Lascia vuoto per auto-riconoscimento")
        self.entry_excel.grid(row=1, column=1, padx=(0, 10), pady=10, sticky="ew")
        ctk.CTkButton(dir_frame, text="Sfoglia...", command=self.browse_excel).grid(row=1, column=2, padx=20, pady=10)

        action_frame = ctk.CTkFrame(self.frame_elaborazione)
        action_frame.grid(row=2, column=0, padx=30, pady=20, sticky="ew")
        action_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.btn_start = ctk.CTkButton(action_frame, text="AVVIA ELABORAZIONE", height=50, 
                                       font=ctk.CTkFont(size=18, weight="bold"), fg_color="green", hover_color="darkgreen",
                                       command=self.start_pipeline)
        self.btn_start.grid(row=0, column=0, padx=(50, 10), pady=30, sticky="ew")

        self.btn_stop = ctk.CTkButton(action_frame, text="FERMA ELABORAZIONE", height=50, 
                                       font=ctk.CTkFont(size=18, weight="bold"), fg_color="red", hover_color="darkred",
                                       command=self.stop_pipeline, state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=(10, 50), pady=30, sticky="ew")
        
        self.lbl_status = ctk.CTkLabel(action_frame, text="Stato: Pronto all'esecuzione.", font=ctk.CTkFont(size=14))
        self.lbl_status.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 10))
        
        self.progress_bar = ctk.CTkProgressBar(action_frame)
        self.progress_bar.grid(row=2, column=0, columnspan=2, padx=50, pady=(0, 30), sticky="ew")
        self.progress_bar.set(0)

    def browse_input(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_input.delete(0, "end")
            self.entry_input.insert(0, folder)

    def browse_excel(self):
        file = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        if file:
            self.entry_excel.delete(0, "end")
            self.entry_excel.insert(0, file)

    def setup_monitoraggio(self):
        lbl = ctk.CTkLabel(self.frame_monitoraggio, text="Monitoraggio Dati Estratti", font=ctk.CTkFont(size=24, weight="bold"))
        lbl.grid(row=0, column=0, padx=30, pady=(30, 20), sticky="w")
        
        self.info_lbl = ctk.CTkLabel(self.frame_monitoraggio, text="I risultati appariranno qui a fine elaborazione.", text_color="gray")
        self.info_lbl.grid(row=1, column=0, padx=30, pady=5, sticky="w")
        
        self.scroll_data = ctk.CTkScrollableFrame(self.frame_monitoraggio)
        self.scroll_data.grid(row=2, column=0, padx=30, pady=10, sticky="nsew")
        self.scroll_data.grid_columnconfigure((0,1,2,3,4), weight=1)
        
        self.update_monitoraggio([]) # Initialize empty table

    def update_monitoraggio(self, results):
        # Clear child widgets
        for widget in self.scroll_data.winfo_children():
            widget.destroy()

        headers = ["File Originale", "Barcode", "Confidence %", "Discrepanze Excel", "Stato"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.scroll_data, text=h, font=ctk.CTkFont(weight="bold")).grid(row=0, column=i, padx=5, pady=5)
            
        for r, row in enumerate(results, start=1):
            color = "red" if "ERROR" in row["status"] else "white"
            ctk.CTkLabel(self.scroll_data, text=row["original_file"], text_color=color).grid(row=r, column=0, padx=5, pady=5)
            ctk.CTkLabel(self.scroll_data, text=row["barcode"], text_color=color).grid(row=r, column=1, padx=5, pady=5)
            ctk.CTkLabel(self.scroll_data, text=row["confidence"], text_color=color).grid(row=r, column=2, padx=5, pady=5)
            ctk.CTkLabel(self.scroll_data, text=row["discrepancy"], text_color=color).grid(row=r, column=3, padx=5, pady=5)
            ctk.CTkLabel(self.scroll_data, text=row["status"], text_color=color).grid(row=r, column=4, padx=5, pady=5)

    def setup_impostazioni(self):
        lbl = ctk.CTkLabel(self.frame_impostazioni, text="Impostazioni OCR e LLM", font=ctk.CTkFont(size=24, weight="bold"))
        lbl.grid(row=0, column=0, padx=30, pady=(30, 20), sticky="w")
        
        settings_frame = ctk.CTkFrame(self.frame_impostazioni)
        settings_frame.grid(row=1, column=0, padx=30, pady=10, sticky="ew")
        
        ctk.CTkLabel(settings_frame, text="Pipeline Selezionata:").grid(row=0, column=0, padx=20, pady=20)
        self.pipeline_switch = ctk.CTkSwitch(settings_frame, text="Usa Vision LLM (Invece di docTR)")
        self.pipeline_switch.grid(row=0, column=1, padx=20, pady=20)
        if self.use_vision:
            self.pipeline_switch.select()
        
        ctk.CTkLabel(settings_frame, text="Modello LLM Locale (Ollama):").grid(row=1, column=0, padx=20, pady=20)
        self.entry_model = ctk.CTkEntry(settings_frame)
        self.entry_model.insert(0, self.llm_config.get("model", "llama3.2"))
        self.entry_model.grid(row=1, column=1, padx=20, pady=20, sticky="ew")
        
        btn_save = ctk.CTkButton(self.frame_impostazioni, text="Salva Impostazioni", command=self.save_settings)
        btn_save.grid(row=2, column=0, padx=30, pady=20, sticky="w")

    def setup_log(self):
        lbl = ctk.CTkLabel(self.frame_log, text="Log di Esecuzione", font=ctk.CTkFont(size=24, weight="bold"))
        lbl.grid(row=0, column=0, padx=30, pady=(30, 20), sticky="w")
        
        self.textbox_log = ctk.CTkTextbox(self.frame_log, font=("Consolas", 12))
        self.textbox_log.grid(row=1, column=0, padx=30, pady=(0, 30), sticky="nsew")
        self.textbox_log.insert("0.0", "--- Inizio Log ---\nAttesa avvio elaborazione...\n")
        self.textbox_log.configure(state="disabled")

    def append_log(self, text):
        self.textbox_log.configure(state="normal")
        self.textbox_log.insert("end", text + "\n")
        self.textbox_log.see("end")
        self.textbox_log.configure(state="disabled")

    # --- Pipeline execution ---
    def start_pipeline(self):
        if self.pipeline_thread and self.pipeline_thread.is_alive():
            return

        input_dir = self.entry_input.get()
        excel_file = self.entry_excel.get()
        use_vision = self.pipeline_switch.get() == 1

        self.btn_start.configure(state="disabled", text="ELABORAZIONE IN CORSO...", fg_color="gray")
        self.btn_stop.configure(state="normal", text="FERMA ELABORAZIONE", fg_color="red")
        self.progress_bar.set(0)
        self.lbl_status.configure(text="Stato: Avvio in corso...")
        
        self.textbox_log.configure(state="normal")
        self.textbox_log.delete("0.0", "end")
        self.textbox_log.configure(state="disabled")

        # Verifica connessione a Ollama (LLM)
        base_url = self.llm_config.get("base_url", "http://localhost:11434/v1")
        test_url = base_url.replace("/v1", "")
        import urllib.request
        import urllib.error
        try:
            urllib.request.urlopen(test_url, timeout=2)
        except urllib.error.URLError:
            self.append_log("Ollama non risponde. Tentativo di avvio del servizio in background...")
            import subprocess
            try:
                # Windows specific flag to hide the console window
                CREATE_NO_WINDOW = 0x08000000
                subprocess.Popen(["ollama", "serve"], creationflags=CREATE_NO_WINDOW)
                self.append_log("Servizio Ollama avviato con successo. Attendo boot...")
                import time
                time.sleep(3)  # Diamo tempo al server di avviarsi
            except Exception as e:
                messagebox.showerror("Errore LLM", f"Impossibile comunicare con il server LLM (Ollama) e impossibile avviarlo automaticamente.\nAssicurati che Ollama sia installato.\n\nErrore: {e}")
                self.btn_start.configure(state="normal", text="AVVIA ELABORAZIONE", fg_color="green")
                self.btn_stop.configure(state="disabled")
                self.lbl_status.configure(text="Stato: Avvio fallito (LLM offline).")
                return

        self.pipeline_thread = PipelineRunner(input_dir, excel_file, use_vision, self.msg_queue)
        self.pipeline_thread.start()

    def stop_pipeline(self):
        if self.pipeline_thread and self.pipeline_thread.is_alive():
            self.btn_stop.configure(state="disabled", text="INTERRUZIONE...")
            self.lbl_status.configure(text="Stato: Interruzione in corso. Attendi...")
            self.pipeline_thread.stop()

    def process_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                msg_type = msg.get("type")
                
                if msg_type == "log":
                    self.append_log(msg.get("message"))
                elif msg_type == "status":
                    self.lbl_status.configure(text=f"Stato: {msg.get('message')}")
                elif msg_type == "progress":
                    self.progress_bar.set(msg.get("value", 0))
                    if "text" in msg:
                        self.lbl_status.configure(text=f"Stato: {msg.get('text')}")
                elif msg_type == "error":
                    self.append_log(f"ERRORE CRITICO: {msg.get('message')}")
                    messagebox.showerror("Errore Pipeline", msg.get("message"))
                elif msg_type == "done":
                    self.btn_start.configure(state="normal", text="AVVIA ELABORAZIONE", fg_color="green")
                    self.btn_stop.configure(state="disabled", text="FERMA ELABORAZIONE", fg_color="red")
                    self.show_monitoraggio()
                    results = msg.get("results", [])
                    self.update_monitoraggio(results)
                    if results:
                        self.info_lbl.configure(text=f"Trovati {len(results)} risultati.")
                    else:
                        self.info_lbl.configure(text="Elaborazione terminata con errori o senza esiti.")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)

    # --- Navigation Logic ---
    def _hide_all_frames(self):
        for frame in self.frames.values():
            frame.grid_forget()
        
        for btn in [self.btn_elaborazione, self.btn_monitoraggio, self.btn_impostazioni, self.btn_log]:
            btn.configure(fg_color=("gray75", "gray25"))

    def show_elaborazione(self):
        self._hide_all_frames()
        self.frame_elaborazione.grid(row=0, column=1, sticky="nsew")
        self.btn_elaborazione.configure(fg_color=("gray75", "gray30"))

    def show_monitoraggio(self):
        self._hide_all_frames()
        self.frame_monitoraggio.grid(row=0, column=1, sticky="nsew")
        self.btn_monitoraggio.configure(fg_color=("gray75", "gray30"))

    def show_impostazioni(self):
        self._hide_all_frames()
        self.frame_impostazioni.grid(row=0, column=1, sticky="nsew")
        self.btn_impostazioni.configure(fg_color=("gray75", "gray30"))

    def show_log(self):
        self._hide_all_frames()
        self.frame_log.grid(row=0, column=1, sticky="nsew")
        self.btn_log.configure(fg_color=("gray75", "gray30"))

if __name__ == "__main__":
    app = App()
    app.mainloop()
