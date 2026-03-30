import pytesseract
from PIL import Image
import io
import re

class OCRProcessor:
    def extract_from_image(self, image_bytes):
        image = Image.open(io.BytesIO(image_bytes))

        text = pytesseract.image_to_string(image)

        # cari angka
        amounts = re.findall(r'\d+[.,]?\d+', text)

        amounts = [float(a.replace('.', '').replace(',', '.')) for a in amounts]

        largest = max(amounts) if amounts else 0

        return {
            "text": text,
            "amounts": amounts,
            "largest_amount": largest,
            "date": "-"
        }