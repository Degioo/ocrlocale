import os
import cv2
import tempfile
import logging
from pathlib import Path
from glmocr import GlmOcr
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from app.utils.llm_parser import get_parser

logger = logging.getLogger("Extraction")

class GLMOCRExtractor:
    def __init__(self, config=None):
        logger.info("[*] Initializing GLM-OCR Extractor...")
        # config is expected to have 'base_url' etc, but glmocr uses config.yaml by default.
        # layout_device="cpu" so we don't need a huge GPU for layout detection on the client side
        self.glm_parser = GlmOcr(layout_device="cpu")
        
        # We still need LLMParser to extract the JSON from the Markdown produced by GLM-OCR
        self.llm_parser = get_parser(
            api_key=config.get("api_key") if config else None,
            base_url=config.get("base_url", "http://ocr_glm:8080/v1") if config else "http://ocr_glm:8080/v1",
            model=config.get("model", "glm-ocr") if config else "glm-ocr",
            timeout=config.get("timeout", 120) if config else 120
        )
        
        default_fields = [
            "Avvertenze", "Barcode", "Data_Preparazione", 
            "Dosaggio", "Dottore", "Ingredienti", 
            "Paziente", "Scadenza", "Tot"
        ]
        
        import json
        fields_path = Path("fields.json")
        if fields_path.exists():
            try:
                with open(fields_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "target_fields" in data:
                        default_fields = data["target_fields"]
            except Exception as e:
                logger.warning(f"Failed to load fields.json: {e}")

        self.fields = config.get("target_fields", default_fields) if config else default_fields

    def extract_full_pipeline(self, img_array):
        """Processes a single numpy image array using GLM-OCR and extracts JSON."""
        if img_array is None or img_array.size == 0:
            return {"error": "Empty image array"}, 0.0
            
        try:
            # 1. Save img_array to a temp file because glmocr expects a file path
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                tmp_path = tmp_file.name
                # Convert RGB to BGR for OpenCV encoding
                bgr_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                cv2.imwrite(tmp_path, bgr_img)
            
            # 2. Parse using GLM-OCR
            logger.info(f"[*] Calling GLM-OCR for image parsing...")
            result = self.glm_parser.parse(tmp_path)
            markdown_text = result.markdown_result
            
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
                
            # 3. Use LLM to extract JSON from Markdown
            logger.info(f"[*] Calling vLLM to extract fields from Markdown...")
            extracted_json = self.llm_parser.extract_fields(markdown_text, self.fields)
            
            # mean_conf is hard to get from GLM-OCR natively without deeper inspection, defaulting to 1.0
            return extracted_json, 1.0
            
        except Exception as e:
            logger.error(f"[!] GLM-OCR Pipeline Failed: {e}")
            return {"error": str(e)}, 0.0

# Keeping dummy classes so pipeline.py doesn't crash if imported, but we will modify pipeline.py anyway
class OCREngine: pass
class LLMExtractor: pass
class VisionExtractor: pass
