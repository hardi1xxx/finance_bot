import pytesseract
import cv2
import numpy as np
from PIL import Image
import io

class OCRProcessor:
    def __init__(self):
        # Konfigurasi Tesseract
        self.custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,RpTotal: -'

    def preprocess_image(self, image_bytes: bytes) -> np.ndarray:
        """Preprocess image for better OCR"""
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh)
        
        return denoised

    def extract_from_image(self, image_bytes: bytes) -> dict:
        """Extract data from receipt image"""
        processed_img = self.preprocess_image(image_bytes)
        
        # OCR
        text = pytesseract.image_to_string(processed_img, config=self.custom_config)
        
        # Parse data
        amounts = parse_amount(text)
        date = parse_date(text)
        
        return {
            'text': text,
            'amounts': amounts,
            'date': date,
            'largest_amount': amounts[0][1] if amounts else 0
        }