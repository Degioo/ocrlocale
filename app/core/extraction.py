import os
import cv2
import tempfile
import logging
from glmocr import GlmOcr

logger = logging.getLogger("Extraction")

class GLMOCRExtractor:
    def __init__(self, config=None):
        logger.info("[*] Initializing GLM-OCR Extractor on GPU...")
        # L'utente ha esplicitato layout_device="cuda"
        self.glm_parser = GlmOcr(layout_device="cuda")

    def extract_markdown(self, img_array):
        """Processes a single numpy image array using GLM-OCR and extracts Markdown."""
        if img_array is None or img_array.size == 0:
            return "Errore: Immagine vuota"
            
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                tmp_path = tmp_file.name
                bgr_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                cv2.imwrite(tmp_path, bgr_img)
            
            logger.info(f"[*] Calling GLM-OCR for image parsing...")
            result = self.glm_parser.parse(tmp_path)
            markdown_text = result.markdown_result
            
            try:
                os.unlink(tmp_path)
            except:
                pass
                
            return markdown_text
            
        except Exception as e:
            logger.error(f"[!] GLM-OCR Pipeline Failed: {e}")
            return f"Errore nell'estrazione OCR: {str(e)}"
