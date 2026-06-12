import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import io
import re
import logging
import numpy as np

logger = logging.getLogger(__name__)

TOTAL_KEYWORDS = [
    'total', 'jumlah', 'grand total', 'subtotal', 'sub total',
    'bayar', 'tagihan', 'amount', 'charge', 'tunai', 'cash',
    'total bayar', 'harus dibayar', 'yg harus dibayar'
]

NOISE_KEYWORDS = [
    'npwp', 'kode', 'no.', 'nomor', 'struk', 'kasir',
    'telepon', 'telp', 'hp', 'member', 'id', 'ref'
]

class OCRProcessor:
    def preprocess_image(self, image):
        if image.mode != 'L':
            image = image.convert('L')

        # Resize untuk resolusi lebih baik (min 1000px tinggi)
        w, h = image.size
        if h < 1000:
            scale = 1000 / h
            image = image.resize((int(w * scale), 1000), Image.LANCZOS)

        # Auto-contrast sebelum enhance
        image = ImageOps.autocontrast(image, cutoff=2)

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.5)

        # Sharpen
        image = image.filter(ImageFilter.SHARPEN)
        image = image.filter(ImageFilter.SHARPEN)  # double sharpen untuk struk buram

        # Threshold binarization — struk thermal sering abu-abu
        threshold = 140
        image = image.point(lambda p: 255 if p > threshold else 0, '1').convert('L')

        return image

    def parse_amount(self, raw: str) -> float | None:
        """Konversi string angka format Indonesia ke float."""
        s = raw.strip()
        # Hapus karakter non-numerik kecuali titik dan koma
        s = re.sub(r'[^\d.,]', '', s)
        if not s:
            return None

        try:
            # Format: 1.234.567 atau 1.234.567,89
            if re.match(r'^\d{1,3}(\.\d{3})+(,\d{1,2})?$', s):
                s = s.replace('.', '').replace(',', '.')
                return float(s)

            # Format: 1,234,567 atau 1,234,567.89
            if re.match(r'^\d{1,3}(,\d{3})+(\.\d{1,2})?$', s):
                s = s.replace(',', '')
                return float(s)

            # Koma sebagai desimal: 12345,89
            if re.match(r'^\d+(,\d{1,2})$', s):
                return float(s.replace(',', '.'))

            # Plain integer / decimal
            return float(s.replace(',', ''))
        except ValueError:
            return None

    def extract_from_image(self, image_bytes: bytes) -> dict:
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = self.preprocess_image(image)

            # Mode 1: baca seluruh teks termasuk huruf (untuk konteks keyword)
            text_full = pytesseract.image_to_string(
                image,
                lang='ind+eng',
                config='--oem 3 --psm 6'
            )
            logger.debug(f"OCR full text:\n{text_full}")

            # Mode 2: fokus baca angka saja (lebih akurat untuk nominal)
            text_num = pytesseract.image_to_string(
                image,
                lang='ind+eng',
                config=r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,: '
            )

            lines = text_full.splitlines()
            total_amount = None
            fallback_amounts = []

            for line in lines:
                line_lower = line.lower()

                # Skip baris yang kemungkinan noise (kode, nomor referensi, dll)
                if any(noise in line_lower for noise in NOISE_KEYWORDS):
                    continue

                # Cari angka di baris ini
                numbers = re.findall(
                    r'\b(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d{4,})\b',
                    line
                )

                parsed = [self.parse_amount(n) for n in numbers]
                valid = [a for a in parsed if a and a >= 100]  # minimal Rp 100

                if not valid:
                    continue

                candidate = max(valid)  # ambil angka terbesar di baris ini

                # Prioritas: baris yang mengandung keyword total/bayar
                if any(kw in line_lower for kw in TOTAL_KEYWORDS):
                    # Update total_amount hanya jika lebih besar
                    # (guard dari pajak/diskon yang muncul setelah TOTAL)
                    if total_amount is None or candidate > total_amount:
                        total_amount = candidate
                        logger.debug(f"  -> TOTAL match: {candidate} dari '{line.strip()}'")
                else:
                    fallback_amounts.extend(valid)

            # Jika tidak ada keyword total, ambil median atas (bukan max — max sering barcode)
            if total_amount is None and fallback_amounts:
                fallback_amounts.sort(reverse=True)
                # Ambil angka ke-2 terbesar (ke-1 sering nomor struk/kode)
                idx = min(1, len(fallback_amounts) - 1)
                total_amount = fallback_amounts[idx]
                logger.debug(f"  -> Fallback amount: {total_amount}")

            return {
                'text': text_full.strip(),
                'amounts': fallback_amounts,
                'largest_amount': total_amount or 0,
                'date': self._extract_date(text_full),
                'description': self._extract_merchant(text_full),
            }

        except Exception as e:
            logger.error(f"OCR error: {e}", exc_info=True)
            return {'text': '', 'amounts': [], 'largest_amount': 0, 'date': '-', 'description': 'OCR'}

    def _extract_date(self, text: str) -> str:
        """Coba ekstrak tanggal dari teks struk."""
        patterns = [
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',
            r'\b(\d{1,2}\s+\w+\s+\d{4})\b',
            r'\b(\d{4}[/-]\d{2}[/-]\d{2})\b',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return '-'

    def _extract_merchant(self, text: str) -> str:
        """Ambil 1-2 baris pertama sebagai nama merchant."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        # Skip baris sangat pendek (sering noise)
        candidates = [l for l in lines[:5] if len(l) > 3]
        if candidates:
            return candidates[0][:40]  # max 40 karakter
        return 'Struk'