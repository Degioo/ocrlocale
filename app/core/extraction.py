import torch
import logging
from doctr.models import ocr_predictor
from doctr.io import DocumentFile

# Import the existing LLM parser 
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from app.utils.llm_parser import get_parser

logger = logging.getLogger("Extraction")

class OCREngine:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"[*] Loading docTR on {self.device}...")
        self.model = ocr_predictor(pretrained=True)
        if self.device.type == "cuda":
             self.model = self.model.cuda()

    def process_image(self, img_array):
        """Processes a single numpy image array. Returns (text, average_confidence)."""
        try:
            # DocumentFile expects a list of images
            res = self.model([img_array])
            
            full_text = ""
            confidences = []
            for page in res.pages:
                for block in page.blocks:
                    for line in block.lines:
                        for w in line.words:
                            confidences.append(w.confidence)
                        line_text = " ".join([w.value for w in line.words])
                        full_text += line_text + "\n"
                        
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            return full_text.strip(), round(avg_conf, 4)
        except Exception as e:
            logger.error(f"[!] OCR Failed: {e}")
            return "", 0.0


class LLMExtractor:
    def __init__(self, config):
        """
        config dict with: api_key, base_url, model, local_model_path, timeout
        """
        self.parser = get_parser(
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            model=config.get("model"),
            local_model_path=config.get("local_model_path"),
            timeout=config.get("timeout", 120)
        )
        default_fields = [
            "Avvertenze", "Barcode", "Data_Preparazione", 
            "Dosaggio", "Dottore", "Ingredienti", 
            "Paziente", "Scadenza", "Tot"
        ]
        
        import json
        from pathlib import Path
        fields_path = Path("fields.json")
        if fields_path.exists():
            try:
                with open(fields_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "target_fields" in data:
                        default_fields = data["target_fields"]
            except Exception as e:
                logger.warning(f"Failed to load fields.json: {e}")

        self.fields = config.get("target_fields", default_fields)

    def extract(self, text):
        if not text:
             return {"error": "Empty OCR text"}
             
        try:
             logger.info("[*] Calling LLM for field extraction...")
             return self.parser.extract_fields(text, self.fields)
        except Exception as e:
             logger.error(f"[!] LLM Extraction Error: {e}")
             return {"error": str(e)}

class VisionExtractor:
    def __init__(self, config):
        """
        config dict with: api_key, base_url, model, local_model_path, timeout
        """
        self.parser = get_parser(
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            model=config.get("model", "moondream"),
            local_model_path=config.get("local_model_path"),
            timeout=config.get("timeout", 180) # vision can be slower
        )
        default_fields = [
            "Avvertenze", "Barcode", "Data_Preparazione", 
            "Dosaggio", "Dottore", "Ingredienti", 
            "Paziente", "Scadenza", "Tot"
        ]
        
        import json
        from pathlib import Path
        fields_path = Path("fields.json")
        if fields_path.exists():
            try:
                with open(fields_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "target_fields" in data:
                        default_fields = data["target_fields"]
            except Exception as e:
                logger.warning(f"Failed to load fields.json: {e}")

        self.fields = config.get("target_fields", default_fields)

    def extract(self, img_array):
        """Processes a single numpy image array using a Vision LLM."""
        if img_array is None or img_array.size == 0:
             return {"error": "Empty image array"}
             
        try:
             import cv2
             import base64
             
             # Convert RGB to BGR for OpenCV encoding
             bgr_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
             success, encoded_image = cv2.imencode('.png', bgr_img)
             if not success:
                 return {"error": "Failed to encode image to PNG"}
                 
             image_base64 = base64.b64encode(encoded_image.tobytes()).decode('utf-8')
             
             logger.info(f"[*] Calling Vision LLM '{self.parser.model}' for direct image extraction...")
             return self.parser.extract_fields_from_image(image_base64, self.fields)
             
        except Exception as e:
             logger.error(f"[!] Vision LLM Extraction Error: {e}")
             return {"error": str(e)}
