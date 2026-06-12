import io
import re
import logging
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

TOTAL_KEYWORDS = [
    'grand total', 'total bayar', 'total harga',
    'harus dibayar', 'yg harus dibayar',
    'jumlah bayar', 'jumlah tagihan',
    'total',
    'jumlah',
    'bayar',
    'tunai',
    'cash',
    'debit',
    'qris',
]

SKIP_KEYWORDS = [
    'npwp', 'sales no', 'reff', 'ref no',
    'telepon', 'telp', 'phone', 'fax',
    'loyalty', 'member', 'cashier',
    'instagram', 'website', 'wifi',
    'terima kasih', 'kami tunggu',
    'price inclusive', 'pb1',
    'pembulatan', 'kembali',
    'jl.', 'jalan', 'kec.', 'kel.',
    'jawa', 'bandung', 'jakarta', 'surabaya',
]

PHONE_PATTERN = re.compile(r'\b0\d{2,3}[-\s]?\d{3,4}[-\s]?\d{3,6}\b')
LONG_NUMBER   = re.compile(r'\b\d{10,}\b')
ZIPCODE       = re.compile(r'\b\d{5}\b')


class OCRProcessor:
    def __init__(self):
        pass

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        if image.mode != 'L':
            image = image.convert('L')

        w, h = image.size
        if h < 1500:
            scale = 1500 / h
            image = image.resize((int(w * scale), 1500), Image.LANCZOS)

        image = ImageOps.autocontrast(image, cutoff=1)
        image = ImageEnhance.Contrast(image).enhance(2.0)
        image = image.filter(ImageFilter.SHARPEN)
        image = image.point(lambda p: 255 if p > 140 else 0, '1').convert('L')

        return image

    def parse_amount(self, raw: str):
        s = re.sub(r'[^\d.,]', '', raw.strip())
        if not s or len(s) < 2:
            return None
        try:
            if re.match(r'^\d{1,3}(\.\d{3})+(,\d{1,2})?$', s):
                return float(s.replace('.', '').replace(',', '.'))
            if re.match(r'^\d{1,3}(,\d{3})+(\.\d{1,2})?$', s):
                return float(s.replace(',', ''))
            if re.match(r'^\d+(,\d{1,2})$', s):
                return float(s.replace(',', '.'))
            cleaned = re.sub(r'[.,]', '', s)
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    def is_noise_line(self, line: str) -> bool:
        line_lower = line.lower()
        if any(kw in line_lower for kw in SKIP_KEYWORDS):
            return True
        if PHONE_PATTERN.search(line):
            return True
        if LONG_NUMBER.search(line):
            return True
        if ZIPCODE.search(line) and not any(c.isalpha() for c in line):
            return True
        return False

    def extract_from_image(self, image_bytes: bytes) -> dict:
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = self.preprocess_image(image)

            # Pass 1: baca full teks untuk konteks keyword
            text = pytesseract.image_to_string(
                image,
                lang='ind+eng',
                config='--oem 3 --psm 6'
            )
            logger.info(f"OCR text:\n{text}")

            lines = text.splitlines()
            total_amount = None
            best_priority = 999
            fallback = []

            for line in lines:
                line_s = line.strip()
                if not line_s:
                    continue
                if self.is_noise_line(line_s):
                    continue

                # Cari semua angka valid di baris ini
                numbers = re.findall(
                    r'\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?\b|\b\d{3,9}\b',
                    line_s
                )
                parsed = [self.parse_amount(n) for n in numbers]
                valid  = [a for a in parsed if a and 500 <= a <= 100_000_000]

                if not valid:
                    continue

                candidate = max(valid)
                line_lower = line_s.lower()

                # Cari keyword total terbaik di baris ini
                matched_priority = None
                for i, kw in enumerate(TOTAL_KEYWORDS):
                    if kw in line_lower:
                        matched_priority = i
                        break

                if matched_priority is not None:
                    if matched_priority < best_priority:
                        best_priority  = matched_priority
                        total_amount   = candidate
                        logger.info(f"TOTAL [{TOTAL_KEYWORDS[matched_priority]}] = {candidate} | '{line_s}'")
                    elif matched_priority == best_priority and candidate > (total_amount or 0):
                        total_amount = candidate
                else:
                    fallback.append(candidate)

            # Fallback: tidak ada keyword total sama sekali
            if total_amount is None and fallback:
                fallback.sort(reverse=True)
                total_amount = fallback[min(1, len(fallback) - 1)]
                logger.info(f"Fallback amount: {total_amount}")

            return {
                'largest_amount': total_amount or 0,
                'description':    self._merchant(lines),
                'date':           self._date(text),
                'text':           text.strip(),
                'amounts':        fallback,
                'error':          '',
            }

        except Exception as e:
            logger.error(f"OCR error: {e}", exc_info=True)
            return self._empty(str(e))

    def _date(self, text: str) -> str:
        for pattern in [
            r'\b(\d{2}-\d{2}-\d{4})\b',
            r'\b(\d{2}/\d{2}/\d{4})\b',
            r'\b(\d{4}-\d{2}-\d{2})\b',
            r'\b(\d{1,2}\s+\w+\s+\d{4})\b',
        ]:
            m = re.search(pattern, text)
            if m:
                return m.group(1)
        return '-'

    def _merchant(self, lines: list) -> str:
        skip = [
            'jl.', 'jalan', 'kec.', 'kel.', 'kota', 'no.',
            'telp', 'hp', 'fax', 'bandung', 'jakarta',
            'reff', 'date', 'tanggal', 'kasir', 'server',
            'dine', 'tipe', 'pelanggan', 'loyalty',
            'invoice', 'receipt', 'struk',
        ]
        for line in lines[:12]:
            s = line.strip()
            if len(s) < 4:
                continue
            if sum(c.isdigit() for c in s) / max(len(s), 1) > 0.4:
                continue
            if any(kw in s.lower() for kw in skip):
                continue
            if sum(not c.isalnum() and c not in ' -.' for c in s) / max(len(s), 1) > 0.35:
                continue
            return s[:40]
        return 'Struk'

    def _empty(self, error: str = '') -> dict:
        return {
            'largest_amount': 0,
            'description':    'Struk',
            'date':           '-',
            'text':           '',
            'amounts':        [],
            'error':          error,
        }