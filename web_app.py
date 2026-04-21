import streamlit as st
import os
import time
import json
import queue
import pandas as pd
from pathlib import Path
from app.core.pipeline import PipelineRunner
from app.core.database import DatabaseManager

st.set_page_config(
    page_title="Piattaforma Operatore ATS",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inizializza session state
if 'page' not in st.session_state:
    st.session_state.page = "setup"
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'progress' not in st.session_state:
    st.session_state.progress = 0.0
if 'status_msg' not in st.session_state:
    st.session_state.status_msg = "Pronto all'esecuzione."
if 'runner_queue' not in st.session_state:
    st.session_state.runner_queue = queue.Queue()
if 'selected_record_id' not in st.session_state:
    st.session_state.selected_record_id = None

db = DatabaseManager()

def load_settings():
    llm_cfg_path = Path("llm_config_local.json")
    if llm_cfg_path.exists():
        with open(llm_cfg_path, 'r') as f:
            cfg = json.load(f)
            is_docker = os.path.exists('/.dockerenv') or os.environ.get('IS_DOCKER') == '1'
            if "localhost" in cfg.get("base_url", "") and is_docker:
                cfg["base_url"] = cfg["base_url"].replace("localhost", "ocr_ollama")
            return cfg
    return {"base_url": "http://ocr_ollama:11434/v1", "model": "llama3.2"}

# --- ROUTER ---

if st.session_state.page == "setup":
    st.title("🌿 Piattaforma OCR Cannabis ATS")
    st.markdown("Benvenuto. Questa piattaforma analizza le prescrizioni scansionate ed estrae i dati automaticamente.")
    
    st.subheader("1. Cartella di Input")
    input_dir = st.text_input("Cartella PDF da analizzare", value=os.path.abspath("input"))
    
    # Analyze folder
    pdf_count = 0
    if os.path.exists(input_dir):
        pdf_count = len(list(Path(input_dir).rglob("*.pdf")))
    
    st.info(f"📁 Trovati **{pdf_count} file PDF** pronti per l'elaborazione.")
    
    st.subheader("2. File Excel di Riferimento (Regionale)")
    excel_file = st.text_input("File Excel di Riconciliazione", value="", help="Lascia vuoto per auto-riconoscimento")
    
    use_vision = st.checkbox("Usa Motore Visivo ad alta precisione (Consigliato per calligrafia pessima)", value=False)
    
    st.markdown("---")
    if st.button("🚀 Avvia Analisi del Lotto", type="primary", use_container_width=True, disabled=(pdf_count==0)):
        st.session_state.input_dir = input_dir
        st.session_state.excel_file = excel_file
        st.session_state.use_vision = use_vision
        st.session_state.page = "processing"
        st.rerun()
        
    st.markdown("---")
    if st.button("Vai alla Dashboard (Senza avviare)"):
        st.session_state.page = "dashboard"
        st.rerun()

elif st.session_state.page == "processing":
    st.title("⚙️ Elaborazione in Corso...")
    
    status_placeholder = st.empty()
    progress_bar = st.progress(st.session_state.progress)
    log_container = st.empty()
    
    if 'runner' not in st.session_state:
        st.session_state.runner = PipelineRunner(
            st.session_state.input_dir, 
            st.session_state.excel_file, 
            st.session_state.use_vision, 
            st.session_state.runner_queue
        )
        st.session_state.runner.start()
        
    runner = st.session_state.runner
    mq = st.session_state.runner_queue
    
    done = False
    with st.spinner("Attendere il termine (i dati vengono salvati nel Database...)"):
        while runner.is_alive() or not mq.empty():
            try:
                msg = mq.get(timeout=0.1)
                mtype = msg.get("type")
                
                if mtype == "log":
                    st.session_state.logs.append(msg.get("message"))
                    log_text = "\n".join(st.session_state.logs[-15:])
                    log_container.code(log_text, language="shell")
                    
                elif mtype == "progress":
                    st.session_state.progress = msg.get("value", 0.0)
                    progress_bar.progress(st.session_state.progress)
                    if "text" in msg:
                        st.session_state.status_msg = msg.get("text")
                        status_placeholder.info(st.session_state.status_msg)
                        
                elif mtype == "status":
                    st.session_state.status_msg = msg.get("message")
                    status_placeholder.info(st.session_state.status_msg)
                    
                elif mtype == "error":
                    st.error(f"ERRORE CRITICO: {msg.get('message')}")
                    
                elif mtype == "done":
                    done = True
                    
            except queue.Empty:
                time.sleep(0.1)
                
    if done or not runner.is_alive():
        del st.session_state.runner
        st.success("Elaborazione Terminata!")
        time.sleep(1)
        st.session_state.page = "dashboard"
        st.rerun()

elif st.session_state.page == "dashboard":
    st.title("🗃️ Dashboard Validazione OCR Regionale")
    
    records = db.get_all_prescriptions()
    
    # --- KPI Metrics ---
    total = len(records)
    da_verificare = sum(1 for r in records if r["status"] == "Da Verificare")
    avg_conf = sum(r["mean_ocr_confidence"] for r in records) / total if total > 0 else 0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📄 Prescrizioni Totali", total)
    m2.metric("⚠️ Da Verificare", da_verificare, delta="-Rimanenti", delta_color="inverse" if da_verificare > 0 else "normal")
    m3.metric("✅ Approvate", total - da_verificare)
    m4.metric("🎯 Confidenza Media", f"{avg_conf*100:.1f}%")
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns([5, 2, 2])
    with col1:
        st.markdown("**Elenco documenti pronti per la revisione:**")
    with col2:
        if records:
            # Generate Excel strictly from DB
            from io import BytesIO
            import pandas as pd
            
            flat_records = []
            for r in records:
                row_data = {"DB_Status": r["status"], "Original_File": r["original_file"], "Confidence": f"{r['mean_ocr_confidence']*100:.1f}%"}
                try:
                    js = json.loads(r["verified_data_json"])
                    row_data.update(js)
                except:
                    pass
                flat_records.append(row_data)
                
            df_export = pd.DataFrame(flat_records)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Esportazione DB')
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 Esporta in Excel",
                data=excel_data,
                file_name=f"export_ats_cannabis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
    with col3:
        if st.button("⬅️ Torna alla Home", use_container_width=True):
            st.session_state.page = "setup"
            st.rerun()
            
    if not records:
        st.info("Nessuna elaborazione presente nel Database.")
    else:
        # Display as a table with Action button
        for r in records:
            status_color = "🔴" if r["status"] == "Da Verificare" else "🟢"
            with st.container(border=True):
                r_col1, r_col2, r_col3, r_col4, r_col5 = st.columns([3, 2, 2, 2, 1])
                r_col1.markdown(f"📄 **{r['original_file']}**")
                r_col2.text(f"Pag. {r['page']} | {r['mean_ocr_confidence']*100:.0f}%")
                r_col3.text(f"Cod: {r['barcode']}")
                r_col4.markdown(f"{status_color} **{r['status']}**")
                
                if r_col5.button("Verifica", key=f"btn_{r['id']}", type="primary" if r["status"] == "Da Verificare" else "secondary", use_container_width=True):
                    st.session_state.selected_record_id = r['id']
                    st.session_state.page = "editor"
                    st.rerun()

elif st.session_state.page == "editor":
    st.title("🔍 Revisione Prescrizione (Split-View)")
    
    record_id = st.session_state.selected_record_id
    records = db.get_all_prescriptions()
    record = next((r for r in records if r["id"] == record_id), None)
    
    if not record:
        st.error("Record non trovato.")
        if st.button("Torna alla Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()
    else:
        # Carica il JSON modificabile (se già verificato, usa quello verificato, altrimenti originale)
        data_dict = json.loads(record["verified_data_json"])
        
        c_left, c_right = st.columns([1, 1])
        
        with c_left:
            st.subheader("Dati Estratti (Modificabili)")
            form_data = {}
            with st.form(key="validation_form"):
                for key, val in data_dict.items():
                    # Handle booleans and strings
                    if isinstance(val, bool):
                        form_data[key] = st.selectbox(key, [True, False], index=0 if val else 1)
                    else:
                        form_data[key] = st.text_input(key, value=str(val) if val is not None else "")
                        
                submit_btn = st.form_submit_button("✅ Salva e Approva", type="primary", use_container_width=True)
                
            if submit_btn:
                # Ripuliamo null string e typecasting basic
                for k, v in form_data.items():
                    if v == "" or v == "None":
                        form_data[k] = None
                        
                db.update_verification(record_id, form_data)
                st.success("Record aggiornato e approvato nel Database Locale!")
                time.sleep(1)
                st.session_state.page = "dashboard"
                st.rerun()
                
            if st.button("⬅️ Annulla e torna alla Dashboard"):
                st.session_state.page = "dashboard"
                st.rerun()
                
        with c_right:
            st.subheader("Documento Originale")
            img_path = record["image_path"]
            if os.path.exists(img_path):
                with st.container(border=True):
                    st.image(img_path, use_column_width=True)
            else:
                st.warning(f"Immagine non trovata nel percorso: {img_path}")
