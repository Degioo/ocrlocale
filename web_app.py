import streamlit as st
import os
import time
import json
import queue
import pandas as pd
from pathlib import Path
from app.core.pipeline import PipelineRunner

st.set_page_config(
    page_title="OCR Prescrizioni Cannabis",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inizializza session state
if 'pipeline_running' not in st.session_state:
    st.session_state.pipeline_running = False
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'progress' not in st.session_state:
    st.session_state.progress = 0.0
if 'status_msg' not in st.session_state:
    st.session_state.status_msg = "Pronto all'esecuzione."
if 'results' not in st.session_state:
    st.session_state.results = []

def load_settings():
    llm_cfg_path = Path("llm_config_local.json")
    if llm_cfg_path.exists():
        with open(llm_cfg_path, 'r') as f:
            cfg = json.load(f)
            if "localhost" in cfg.get("base_url", "") and os.path.exists('/.dockerenv'):
                cfg["base_url"] = cfg["base_url"].replace("localhost", "ocr_ollama")
            return cfg
    # Defaulting to the docker-compose ollama internal network name
    return {"base_url": "http://ocr_ollama:11434/v1", "model": "llama3.2"}

def save_settings(cfg):
    with open("llm_config_local.json", 'w') as f:
        json.dump(cfg, f, indent=4)

# Sidebar
with st.sidebar:
    st.title("🌿 OCR Cannabis")
    st.subheader("Impostazioni")
    
    cfg = load_settings()
    
    use_vision = st.checkbox("Usa Vision LLM (Invece di docTR)", value=False)
    
    model_name = st.text_input("Modello LLM (Ollama)", value=cfg.get("model", "llama3.2"))
    base_url = st.text_input("URL Ollama", value=cfg.get("base_url", "http://ocr_ollama:11434/v1"))
    
    if st.button("Salva Impostazioni"):
        cfg["model"] = model_name
        cfg["base_url"] = base_url
        save_settings(cfg)
        st.success("Impostazioni salvate!")
        
    st.markdown("---")
    st.caption("Directory Mappate da Host:")
    st.code("/app/input\n/app/output")

# Main Content
st.title("Cruscotto Elaborazione")

# Input forms
col1, col2 = st.columns(2)
with col1:
    input_dir = st.text_input("Cartella PDF (interno Docker)", value=os.path.abspath("input"))
with col2:
    excel_file = st.text_input("File Excel (interno Docker)", value="", help="Lascia vuoto per auto-riconoscimento in /input")

st.markdown("---")

# Execution Area
start_col, stop_col = st.columns([1, 1])

msg_queue = queue.Queue()

if start_col.button("🚀 AVVIA ELABORAZIONE", type="primary", use_container_width=True, disabled=st.session_state.pipeline_running):
    st.session_state.pipeline_running = True
    st.session_state.logs = []
    st.session_state.progress = 0.0
    st.session_state.status_msg = "Avvio in corso..."
    st.session_state.results = []
    st.rerun()

# Execution context
if st.session_state.pipeline_running:
    
    # Check if Ollama is reachable
    cfg = load_settings()
    
    status_placeholder = st.empty()
    progress_bar = st.progress(st.session_state.progress)
    log_container = st.empty()
    
    # We run the pipeline synchronously within Streamlit but updating placeholders
    runner = PipelineRunner(input_dir, excel_file, use_vision, msg_queue)
    runner.start()
    
    done = False
    
    while runner.is_alive() or not msg_queue.empty():
        try:
            msg = msg_queue.get(timeout=0.1)
            mtype = msg.get("type")
            
            if mtype == "log":
                st.session_state.logs.append(msg.get("message"))
                # Mostra solo gli ultimi 15 log per non ingolfare il browser
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
                st.session_state.logs.append(f"ERROR: {msg.get('message')}")
                
            elif mtype == "done":
                st.session_state.results = msg.get("results", [])
                done = True
                
        except queue.Empty:
            pass
            
    # Alla fine
    st.session_state.pipeline_running = False
    status_placeholder.success("Elaborazione Terminata!")
    st.rerun()

# Results Display
if not st.session_state.pipeline_running and st.session_state.results:
    st.subheader("📊 Risultati Monitoraggio")
    
    df = pd.DataFrame(st.session_state.results)
    
    # Color coding
    def color_status(val):
        color = 'red' if 'ERROR' in str(val) else 'green'
        return f'color: {color}'
        
    styled_df = df.style.map(color_status, subset=['status'])
    st.dataframe(styled_df, use_container_width=True)

elif not st.session_state.pipeline_running:
    st.info("Attesa avvio...")
