import io
import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import transforms, models
from doctr.io import DocumentFile
from deskew import determine_skew
from PIL import Image
from pyzbar.pyzbar import decode as decode_barcode
import logging

logger = logging.getLogger("Preprocessing")

# --- Models Definitions ---
def get_barcode_net():
    model = models.resnet18(weights=None)
    num_ftrs = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Linear(num_ftrs, 128),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(128, 2),
        nn.Sigmoid()
    )
    return model

def get_crop_net():
    model = models.resnet18(weights=None)
    num_ftrs = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Linear(num_ftrs, 128),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(128, 2),
        nn.Sigmoid()
    )
    return model


class ImageEnhancer:
    @staticmethod
    def get_deskew_angle(cv_img):
        if len(cv_img.shape) == 3:
            gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)
        else:
            gray = cv_img
            
        h, w = gray.shape
        if w > 800:
            scale = 800 / w
            gray = cv2.resize(gray, None, fx=scale, fy=scale)
            
        return determine_skew(gray)

    @staticmethod
    def apply_deskew(cv_img, angle):
        if angle is None or abs(angle) < 0.1:
            return cv_img

        (h, w) = cv_img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        abs_cos = abs(M[0, 0])
        abs_sin = abs(M[0, 1])
        new_w = int(h * abs_sin + w * abs_cos)
        new_h = int(h * abs_cos + w * abs_sin)
        
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]
        
        return cv2.warpAffine(cv_img, M, (new_w, new_h), 
                             flags=cv2.INTER_CUBIC, 
                             borderMode=cv2.BORDER_CONSTANT, 
                             borderValue=(255, 255, 255))

class BarcodeScanner:
    def __init__(self, model_path="barcode_model.pth"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        try:
            import os
            if os.path.exists(model_path):
                self.model = get_barcode_net()
                self.model.load_state_dict(torch.load(model_path, map_location=self.device))
                self.model.to(self.device)
                self.model.eval()
                logger.info("[+] Barcode CNN Model loaded successfully.")
            else:
                logger.warning(f"[!] Barcode model not found at {model_path}. Using standard scan.")
        except Exception as e:
            logger.error(f"[!] Barcode model load error: {e}")

    def predict_center(self, cv_img):
        h, w = cv_img.shape[:2]
        img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        
        transform = transforms.Compose([
            transforms.Resize((512, 512)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        
        img_tensor = transform(pil_img).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(img_tensor)
            norm_x, norm_y = outputs.cpu().numpy()[0]
            
        return int(norm_x * w), int(norm_y * h)

    def scan(self, img):
        if img.dtype != np.uint8:
            img = (img * 255).astype(np.uint8) if img.max() <= 1.0 else img.astype(np.uint8)

        crop = img
        if self.model:
            FIXED_W, FIXED_H = 2279, 446
            h, w = img.shape[:2]
            try:
                cx, cy = self.predict_center(img)
                top_left_x = max(0, cx - FIXED_W // 2)
                top_left_y = max(0, cy - FIXED_H // 2)
                bottom_right_x = min(w, cx + FIXED_W // 2)
                bottom_right_y = min(h, cy + FIXED_H // 2)
                
                if bottom_right_x > top_left_x and bottom_right_y > top_left_y:
                     crop = img[top_left_y:bottom_right_y, top_left_x:bottom_right_x]
            except Exception as e:
                pass
        
        if len(crop.shape) == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop

        decoded_objects = decode_barcode(gray)
        found_id = None
        
        if decoded_objects:
            vals = [b.data.decode("utf-8") for b in decoded_objects if b.data.decode("utf-8").isdigit()]
            part_5 = [c for c in vals if len(c) == 5]
            part_10 = [c for c in vals if len(c) == 10]
            part_15 = [c for c in vals if len(c) == 15]
            
            if part_15:
                found_id = part_15[0]
            elif part_5 and part_10:
                 found_id = part_5[0] + part_10[0]
            elif len(vals) >= 2:
                vals_sorted = sorted(vals, key=len)
                if len(vals_sorted) >= 2 and len(vals_sorted[0]) == 5 and len(vals_sorted[1]) == 10:
                     found_id = vals_sorted[0] + vals_sorted[1]
                     
        return found_id

class LabelCropper:
    def __init__(self, model_path="crop_model.pth"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        try:
            import os
            if os.path.exists(model_path):
                self.model = get_crop_net()
                self.model.load_state_dict(torch.load(model_path, map_location=self.device))
                self.model.to(self.device)
                self.model.eval()
                logger.info("[+] Label Crop CNN Model loaded successfully.")
            else:
                logger.warning(f"[!] Crop model not found at {model_path}. Will fallback to full image.")
        except Exception as e:
            logger.error(f"[!] Crop model load error: {e}")

    def predict_center(self, cv_img):
        img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        transform = transforms.Compose([
            transforms.Resize((512, 512)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        img_tensor = transform(pil_img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            outputs = self.model(img_tensor)
            norm_x, norm_y = outputs.cpu().numpy()[0]
        return norm_x, norm_y

    def crop(self, img):
        if not self.model:
            return img # Return full image if no crop model
            
        FIXED_W = 2599
        FIXED_H = 907
        PAD_LEFT = 100
        PAD_RIGHT = 40
        PAD_TOP = 100
        PAD_BOTTOM = 40

        try:
            h, w = img.shape[:2]
            nx, ny = self.predict_center(img)
            cx = int(nx * w)
            cy = int(ny * h)
            
            orig_x1 = cx - FIXED_W // 2
            orig_y1 = cy - FIXED_H // 2
            orig_x2 = cx + FIXED_W // 2
            orig_y2 = cy + FIXED_H // 2
            
            final_x1 = max(0, orig_x1 - PAD_LEFT)
            final_y1 = max(0, orig_y1 - PAD_TOP)
            final_x2 = min(w, orig_x2 + PAD_RIGHT)
            final_y2 = min(h, orig_y2 + PAD_BOTTOM)
            
            crop = img[final_y1:final_y2, final_x1:final_x2]
            return crop
        except Exception as e:
            logger.warning(f"[!] Cropping failed: {e}. Returning original.")
            return img

class PDFProcessor:
    """Handles PDF loading and splitting into images."""
    @staticmethod
    def extract_images(pdf_bytes):
        """Converts raw PDF bytes to numpy images using doctr."""
        return DocumentFile.from_pdf(pdf_bytes)
