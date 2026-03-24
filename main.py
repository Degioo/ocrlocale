import os
import time
import json
import logging
import cv2
from pathlib import Path

# Setup simple root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MainPipeline")

# Suppress annoying warnings
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
import warnings
warnings.filterwarnings("ignore")

from app.core.preprocessing import PDFProcessor, ImageEnhancer, BarcodeScanner, LabelCropper
from app.core.extraction import OCREngine, LLMExtractor, VisionExtractor
from app.core.excel_matcher import ExcelProcessor
from app.core.postprocessing import PDFExporter

# Toggle to switch between docTR+TextLLM and native Vision LLM pipeline
USE_VISION_PIPELINE = False

def main():
    start_time = time.time()
    
    # 1. Configuration & Directories
    input_dir = Path("input")
    output_dir = Path("output")
    images_dir = output_dir / "images"
    final_pdfs_dir = output_dir / "final_pdfs"
    
    for d in [input_dir, images_dir, final_pdfs_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    llm_cfg_path = Path("llm_config_local.json")
    if llm_cfg_path.exists():
        with open(llm_cfg_path, 'r') as f:
            llm_config = json.load(f)
    else:
        llm_config = {"base_url": "http://localhost:11434/v1", "model": "llama3.2"}
        
    # Auto-find a valid Regional Excel file in input dir or root
    excel_file = next(input_dir.glob("*.xlsx"), None) or next(Path(".").glob("*.xlsx"), None)
    if not excel_file:
        logger.error("[!] No Regional Excel file found in input or root directory!")
        return

    # 2. Initialize Models
    logger.info("[*] Initializing Pipeline Modules...")
    enhancer = ImageEnhancer()
    barcode_scanner = BarcodeScanner(model_path="barcode_model.pth")
    cropper = LabelCropper(model_path="crop_model.pth")
    
    if USE_VISION_PIPELINE:
        vision_extractor = VisionExtractor(config=llm_config)
        logger.info(f"[*] Vision Pipeline enabled (Model: {llm_config.get('model')})")
    else:
        ocr_engine = OCREngine()
        llm_extractor = LLMExtractor(config=llm_config)
        
    excel_processor = ExcelProcessor(excel_path=excel_file)
    pdf_exporter = PDFExporter()

    pdf_files = list(input_dir.rglob("*.pdf"))
    if not pdf_files:
        logger.warning(f"[!] No PDFs found in {input_dir} or its subdirectories")
        return
        
    results = []
    saved_images = []

    # 3. Process Pipeline
    for pdf_path in pdf_files:
        logger.info(f"\n[>>>] Processing {pdf_path.name}")
        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
                
            pages = PDFProcessor.extract_images(pdf_bytes)
            logger.info(f"      Loaded {len(pages)} pages.")
            
            for p_idx, page_img in enumerate(pages):
                page_num = p_idx + 1
                logger.info(f"      --- Page {page_num} ---")
                
                # Deskew
                angle = enhancer.get_deskew_angle(page_img)
                deskewed = enhancer.apply_deskew(page_img, angle)
                
                # Barcode Scan
                b_code = barcode_scanner.scan(deskewed)
                barcode_str = b_code if b_code else "undefined"
                logger.info(f"          Barcode: {barcode_str}")
                
                # Naming and Saving Image
                img_name = f"{barcode_str}_{pdf_path.stem}_p{page_num}.png"
                img_path = images_dir / img_name
                
                # Convert RGB to BGR for OpenCV
                bgr_deskewed = cv2.cvtColor(deskewed, cv2.COLOR_RGB2BGR)
                cv2.imwrite(str(img_path), bgr_deskewed, [cv2.IMWRITE_PNG_COMPRESSION, 1])
                saved_images.append(img_path)
                
                # Label Crop & Extraction
                cropped = cropper.crop(deskewed)
                
                if USE_VISION_PIPELINE:
                    # Vision models prefer to see the full context of the page
                    ocr_data = vision_extractor.extract(deskewed)
                    mean_conf = 1.0  # Vision LLMs do not provide character-level confidence
                else:
                    logger.info("          Running Full Page OCR...")
                    full_text, conf_full = ocr_engine.process_image(deskewed)
                    
                    logger.info("          Running Cropped Label OCR...")
                    label_text, conf_label = ocr_engine.process_image(cropped)
                    
                    mean_conf = (conf_full + conf_label) / 2.0
                    
                    combined_text = (
                        f"--- TESTO INTERA RICETTA (Per Timbri/Firme/ecc) ---\n{full_text}\n\n"
                        f"--- TESTO ETICHETTA (Per Dati Specifici Farmaco) ---\n{label_text}"
                    )
                    
                    # LLM Extraction
                    ocr_data = llm_extractor.extract(combined_text)
                
                results.append({
                    "barcode": barcode_str,
                    "original_file": pdf_path.name,
                    "page": page_num,
                    "mean_ocr_confidence": mean_conf,
                    "ocr_data": ocr_data
                })
                
                logger.info(f"          Extraction complete.")
                
        except Exception as e:
            logger.error(f"[!] Critical Error on {pdf_path.name}: {e}")

    # 4. Reconciliation
    logger.info("\n[*] Starting Excel Reconciliation...")
    merged_df = excel_processor.reconcile_and_merge(results)
    
    if merged_df is not None:
        excel_processor.save(merged_df, output_dir / "verified_cannabis_prescriptions.xlsx")

    # 5. Image to PDF Conversion
    logger.info("\n[*] Converting final images back to PDFs...")
    pdf_exporter.images_to_pdfs(saved_images, final_pdfs_dir)
    
    total_time = time.time() - start_time
    logger.info(f"\n[DONE] Pipeline completed in {total_time:.1f}s")


if __name__ == "__main__":
    main()
