import fitz  # PyMuPDF
import numpy as np
import logging

logger = logging.getLogger("Preprocessing")

class PDFProcessor:
    """Handles PDF loading and splitting into images."""
    @staticmethod
    def extract_images(pdf_bytes):
        """Converts raw PDF bytes to numpy images using PyMuPDF."""
        images = []
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # Render at 300 DPI for high quality OCR
                pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                
                # Convert RGBA to RGB if needed
                if pix.n == 4:
                    import cv2
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
                    
                images.append(img)
            doc.close()
        except Exception as e:
            logger.error(f"Error extracting images from PDF: {e}")
        return images
