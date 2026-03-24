import cv2
import logging
from pathlib import Path
from PIL import Image

logger = logging.getLogger("Postprocessing")

class PDFExporter:
    @staticmethod
    def images_to_pdfs(image_paths, output_dir: Path):
        """Converts a list of image paths to single-page PDF files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_paths = []
        
        for img_path in image_paths:
            try:
                # Ensure it's a valid path
                img_path = Path(img_path)
                
                # We want to open with PIL to save as PDF easily
                image = Image.open(img_path)
                
                # Convert RGBA to RGB if necessary for PDF compatibility
                if image.mode == 'RGBA':
                    image = image.convert('RGB')
                    
                pdf_name = f"{img_path.stem}.pdf"
                pdf_path = output_dir / pdf_name
                
                image.save(pdf_path, "PDF", resolution=100.0)
                pdf_paths.append(pdf_path)
                logger.info(f"    [+] Saved {pdf_name}")
                
            except Exception as e:
                logger.error(f"    [!] Failed to convert {img_path.name} to PDF: {e}")
                
        return pdf_paths
