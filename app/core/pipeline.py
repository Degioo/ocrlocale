import os
import time
import json
import logging
import cv2
import threading
from pathlib import Path
from queue import Queue

from app.core.preprocessing import PDFProcessor, ImageEnhancer, BarcodeScanner, LabelCropper
from app.core.extraction import OCREngine, LLMExtractor, VisionExtractor
from app.core.excel_matcher import ExcelProcessor
from app.core.postprocessing import PDFExporter

# We can create a custom logging handler
class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put({"type": "log", "message": msg})


class PipelineRunner(threading.Thread):
    def __init__(self, input_dir: str, excel_file: str, use_vision: bool, msg_queue: Queue):
        super().__init__()
        self._stop_event = threading.Event()
        self.input_dir = Path(input_dir)
        self.excel_file = Path(excel_file) if excel_file else None
        self.use_vision = use_vision
        self.msg_queue = msg_queue
        
        # Setup logger
        self.logger = logging.getLogger("MainPipeline")
        self.logger.setLevel(logging.INFO)
        
        # Remove old handlers to prevent duplicates
        for h in self.logger.handlers[:]:
            self.logger.removeHandler(h)
            
        # Add queue handler
        qh = QueueHandler(self.msg_queue)
        qh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s - %(message)s', datefmt='%H:%M:%S'))
        self.logger.addHandler(qh)

        # Setup persistent file handler
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
        final_pdfs_dir = output_dir / "final_pdfs"
        
        for d in [self.input_dir, images_dir, final_pdfs_dir]:
            d.mkdir(parents=True, exist_ok=True)
            
        llm_cfg_path = Path("llm_config_local.json")
        if llm_cfg_path.exists():
            with open(llm_cfg_path, 'r') as f:
                llm_config = json.load(f)
        else:
            llm_config = {"base_url": "http://localhost:11434/v1", "model": "llama3.2"}

        # Excel file check
        if not self.excel_file or not self.excel_file.exists():
            # Try to find it in input dir or root
            found = next(self.input_dir.glob("*.xlsx"), None) or next(Path(".").glob("*.xlsx"), None)
            if found:
                self.excel_file = found
            
        if not self.excel_file:
            self.logger.error("[!] No Regional Excel file found in input or root directory!")
            self.msg_queue.put({"type": "error", "message": "Nessun file Excel regionale trovato!"})
            self.msg_queue.put({"type": "done", "results": []})
            return

        # Initialize Models
        self.logger.info("[*] Initializing Pipeline Modules...")
        self.msg_queue.put({"type": "status", "message": "Inizializzazione modelli in corso..."})
        
        enhancer = ImageEnhancer()
        barcode_scanner = BarcodeScanner(model_path="barcode_model.pth")
        cropper = LabelCropper(model_path="crop_model.pth")
        
        if self.use_vision:
            vision_extractor = VisionExtractor(config=llm_config)
            self.logger.info(f"[*] Vision Pipeline enabled (Model: {llm_config.get('model')})")
        else:
            ocr_engine = OCREngine()
            llm_extractor = LLMExtractor(config=llm_config)
            
        excel_processor = ExcelProcessor(excel_path=self.excel_file)
        pdf_exporter = PDFExporter()

        pdf_files = list(self.input_dir.rglob("*.pdf"))
        if not pdf_files:
            self.logger.warning(f"[!] No PDFs found in {self.input_dir} or its subdirectories")
            self.msg_queue.put({"type": "error", "message": f"Nessun PDF trovato nella cartella {self.input_dir}"})
            self.msg_queue.put({"type": "done", "results": []})
            return
            
        results = []
        saved_images = []

        total_pdfs = len(pdf_files)

        for i, pdf_path in enumerate(pdf_files):
            if self._stop_event.is_set():
                self.logger.warning("[!] Interruzione richiesta dall'operatore. Arresto del loop sui PDF.")
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
                        self.logger.warning("[!] Arresto del loop sulle pagine.")
                        break
                        
                    page_num = p_idx + 1
                    self.logger.info(f"      --- Page {page_num} ---")
                    
                    # Deskew
                    angle = enhancer.get_deskew_angle(page_img)
                    deskewed = enhancer.apply_deskew(page_img, angle)
                    
                    # Barcode Scan
                    b_code = barcode_scanner.scan(deskewed)
                    barcode_str = b_code if b_code else "undefined"
                    self.logger.info(f"          Barcode: {barcode_str}")
                    
                    # Naming and Saving Image
                    img_name = f"{barcode_str}_{pdf_path.stem}_p{page_num}.png"
                    img_path = images_dir / img_name
                    
                    # Convert RGB to BGR for OpenCV
                    bgr_deskewed = cv2.cvtColor(deskewed, cv2.COLOR_RGB2BGR)
                    cv2.imwrite(str(img_path), bgr_deskewed, [cv2.IMWRITE_PNG_COMPRESSION, 1])
                    saved_images.append(img_path)
                    
                    # Label Crop & Extraction
                    cropped = cropper.crop(deskewed)
                    
                    if self.use_vision:
                        ocr_data = vision_extractor.extract(deskewed)
                        mean_conf = 1.0
                    else:
                        self.logger.info("          Running Full Page OCR...")
                        full_text, conf_full = ocr_engine.process_image(deskewed)
                        
                        self.logger.info("          Running Cropped Label OCR...")
                        label_text, conf_label = ocr_engine.process_image(cropped)
                        
                        mean_conf = (conf_full + conf_label) / 2.0
                        
                        combined_text = (
                            f"--- TESTO INTERA RICETTA (Per Timbri/Firme/ecc) ---\n{full_text}\n\n"
                            f"--- TESTO ETICHETTA (Per Dati Specifici Farmaco) ---\n{label_text}"
                        )
                        
                        ocr_data = llm_extractor.extract(combined_text)
                    
                    results.append({
                        "barcode": barcode_str,
                        "original_file": pdf_path.name,
                        "page": page_num,
                        "mean_ocr_confidence": mean_conf,
                        "ocr_data": ocr_data
                    })
                    
                    self.logger.info(f"          Extraction complete.")
                    
            except Exception as e:
                self.logger.error(f"[!] Critical Error on {pdf_path.name}: {e}")

        self.msg_queue.put({"type": "status", "message": "Riconciliazione Excel in corso..."})
        self.logger.info("\n[*] Starting Excel Reconciliation...")
        merged_df = excel_processor.reconcile_and_merge(results)
        
        discrepancy_report = []
        if merged_df is not None:
            excel_processor.save(merged_df, output_dir / "verified_cannabis_prescriptions.xlsx")
            
            import pandas as pd
            for idx, row in merged_df.iterrows():
                # Check for standard error columns
                has_error = False
                error_msg = "Nessuna"
                
                # Check discrepancy columns
                err_cols = [c for c in merged_df.columns if pd.notnull(row[c]) and row[c] != "" and c.startswith("err_")]
                if err_cols:
                    has_error = True
                    error_msg = " | ".join([f"{c}: {row[c]}" for c in err_cols])
                            
                discrepancy_report.append({
                    "original_file": row.get("original_file", f"riga_{idx}"),
                    "barcode": row.get("barcode", ""),
                    "confidence": f"{row.get('mean_ocr_confidence', 1.0) * 100:.1f}%",
                    "discrepancy": error_msg,
                    "status": "ERROR!" if has_error else "OK"
                })

        self.msg_queue.put({"type": "status", "message": "Conversione in PDF finali..."})
        self.logger.info("\n[*] Converting final images back to PDFs...")
        pdf_exporter.images_to_pdfs(saved_images, final_pdfs_dir)
        
        total_time = time.time() - start_time
        self.logger.info(f"\n[DONE] Pipeline completed in {total_time:.1f}s")
        
        self.msg_queue.put({
            "type": "progress", 
            "value": 1.0,
            "text": f"Elaborazione Completata in {total_time:.1f}s"
        })
        self.msg_queue.put({"type": "done", "results": discrepancy_report if merged_df is not None else []})
