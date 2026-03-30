import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import io
import re
import logging

logger = logging.getLogger(__name__)

class OCRProcessor:
    def preprocess_image(self, image):
        """Preprocess image untuk OCR yang lebih baik"""
        # Convert ke grayscale
        if image.mode != 'L':
            image = image.convert('L')
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2)
        
        # Sharpen
        image = image.filter(ImageFilter.SHARPEN)
        
        return image

    def extract_from_image(self, image_bytes):
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = self.preprocess_image(image)

            # OCR dengan config untuk angka
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,'
            text = pytesseract.image_to_string(image, config=custom_config)

            logger.debug(f"OCR text: {text}")

            # Pattern untuk angka Indonesia (titik ribuan, koma desimal)
            patterns = [
                r'\b(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)\b',  # 1.234.567,89
                r'\b(\d{1,3}(?:,\d{3})*(?:,\d{1,2})?)\b',  # 1,234,567.89
                r'\b(\d+(?:[.,]\d{1,3})*)\b',               # 1234 atau 1.234
                r'\b(\d+)\b'                                # plain numbers
            ]

            amounts = []
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Clean dan convert ke float
                    cleaned = re.sub(r'[^\d,.]', '', match)
                    if ',' in cleaned:
                        cleaned = cleaned.replace('.', '').replace(',', '.')
                    elif '.' in cleaned:
                        parts = cleaned.split('.')
                        if len(parts) > 2:  # ribuan
                            cleaned = cleaned.replace('.', '')
                        else:
                            cleaned = cleaned.replace(',', '.')
                    
                    try:
                        amount = float(cleaned)
                        if amount > 0:
                            amounts.append(amount)
                    except ValueError:
                        continue

            amounts = list(set(amounts))  # Remove duplicates
            largest = max(amounts) if amounts else 0

            return {
                "text": text.strip(),
                "amounts": amounts,
                "largest_amount": largest,
                "date": "-"
            }
        except Exception as e:
            logger.error(f"OCR processing error: {e}")
            return {"text": "", "amounts": [], "largest_amount": 0, "date": "-"}