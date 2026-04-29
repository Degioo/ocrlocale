import os
import time
import logging
import cv2
import threading
from pathlib import Path
from queue import Queue

from app.core.preprocessing import PDFProcessor
from app.core.extraction import GLMOCRExtractor
from app.core.database import DatabaseManager

class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put({"type": "log", "message": msg})

class PipelineRunner(threading.Thread):
    def __init__(self, input_dir: str, msg_queue: Queue):
        super().__init__()
        self._stop_event = threading.Event()
        self.input_dir = Path(input_dir)
        self.msg_queue = msg_queue
        
        self.logger = logging.getLogger("MainPipeline")
        self.logger.setLevel(logging.INFO)
        
        for h in self.logger.handlers[:]:
            self.logger.removeHandler(h)
            
        qh = QueueHandler(self.msg_queue)
        qh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s - %(message)s', datefmt='%H:%M:%S'))
        self.logger.addHandler(qh)

        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(output_dir / "esecuzione_log.txt", mode='a', encoding='utf-8')
        fh.setFormatter(logging.Formatter('======\n%(asctime)s %(levelname)s - %(message)s\n======', datefmt='%Y-%m-%d %H:%M:%S'))
        self.logger.addHandler(fh)

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            self._execute_pipeline()
        except Exception as e:
            self.msg_queue.put({"type": "error", "message": str(e)})
            self.msg_queue.put({"type": "done", "results": []})

    def _execute_pipeline(self):
        start_time = time.time()
        
        output_dir = Path("output")
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
            
        self.logger.info("[*] Initializing GLM-OCR Extractor...")
        self.msg_queue.put({"type": "status", "message": "Inizializzazione modello in corso..."})
        
        extractor = GLMOCRExtractor()
        
        pdf_files = list(self.input_dir.rglob("*.pdf"))
        if not pdf_files:
            self.logger.warning(f"[!] Nessun PDF trovato in {self.input_dir}")
            self.msg_queue.put({"type": "error", "message": f"Nessun PDF trovato nella cartella {self.input_dir}"})
            self.msg_queue.put({"type": "done", "results": []})
            return
            
        total_pdfs = len(pdf_files)
        results = []

        for i, pdf_path in enumerate(pdf_files):
            if self._stop_event.is_set():
                break

            self.logger.info(f"\n[>>>] Processing {pdf_path.name}")
            self.msg_queue.put({
                "type": "progress", 
                "value": i / total_pdfs,
                "text": f"Elaborazione: {pdf_path.name} ({i+1}/{total_pdfs})"
            })
            
            try:
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                    
                pages = PDFProcessor.extract_images(pdf_bytes)
                self.logger.info(f"      Loaded {len(pages)} pages.")
                
                for p_idx, page_img in enumerate(pages):
                    if self._stop_event.is_set():
                        break
                        
                    page_num = p_idx + 1
                    self.logger.info(f"      --- Page {page_num} ---")
                    
                    img_name = f"{pdf_path.stem}_p{page_num}.png"
                    img_path = images_dir / img_name
                    
                    bgr_img = cv2.cvtColor(page_img, cv2.COLOR_RGB2BGR)
                    cv2.imwrite(str(img_path), bgr_img, [cv2.IMWRITE_PNG_COMPRESSION, 1])
                    
                    ocr_markdown = extractor.extract_markdown(page_img)
                    
                    db_manager = DatabaseManager()
                    db_manager.insert_prescription(
                        original_file=pdf_path.name,
                        barcode="N/A", # Rimosso scanner barcode
                        page=page_num,
                        confidence=1.0, # GLM-OCR non restituisce una confidence semplice
                        ocr_markdown=ocr_markdown,
                        image_path=str(img_path)
                    )
                    
                    self.logger.info(f"          Extraction complete and saved to DB.")
                    
            except Exception as e:
                self.logger.error(f"[!] Critical Error on {pdf_path.name}: {e}")

        total_time = time.time() - start_time
        self.logger.info(f"\n[DONE] Pipeline completed in {total_time:.1f}s")
        
        self.msg_queue.put({
            "type": "progress", 
            "value": 1.0,
            "text": f"Elaborazione Completata in {total_time:.1f}s"
        })
        self.msg_queue.put({"type": "done", "results": []})
