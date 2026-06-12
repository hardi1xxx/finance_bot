import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import io
import re
import logging

logger = logging.getLogger(__name__)

TOTAL_KEYWORDS = [
    'grand total', 'total bayar', 'total harga', 'harus dibayar',
    'yg harus dibayar', 'yang harus dibayar',
    'total',      # fallback — setelah yg lebih spesifik
    'jumlah',
    'subtotal',
    'bayar',
    'tagihan',
    'tunai',
    'cash',
    'debit',
    'kartu debit',
    'qris',
]

# Baris yang PASTI bukan nominal transaksi
NOISE_PATTERNS = [
    r'\b0\d{2,3}[-\s]\d{3,4}[-\s]\d{3,6}\b',  # nomor telepon: 0811-3483-516
    r'\bM0\d+\b',                                # kode struk: M025202...
    r'\bSM0\d+\b',                               # sales no
    r'\b\d{10,}\b',                              # barcode / nomor panjang > 9 digit
]

SKIP_LINE_KEYWORDS = [
    'npwp', 'sales no', 'reff no', 'ref no', 'no struk',
    'telepon', 'telp', 'phone', 'hp :', 'fax',
    'loyalty', 'member', 'server', 'cashier', 'kasir :',
    'ig :', 'instagram', 'website', 'wifi',
    'terima kasih', 'kami tunggu', 'barang yang telah',
    'price inclusive', 'pajak', 'pb1',
    'pembulatan',   # biasanya nominal kecil/negatif
]


class OCRProcessor:
    def preprocess_image(self, image):
        if image.mode != 'L':
            image = image.convert('L')

        w, h = image.size
        if h < 1200:
            scale = 1200 / h
            image = image.resize((int(w * scale), 1200), Image.LANCZOS)

        image = ImageOps.autocontrast(image, cutoff=1)

        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)

        image = image.filter(ImageFilter.SHARPEN)

        # Binarization
        image = image.point(lambda p: 255 if p > 150 else 0, '1').convert('L')

        return image

    def parse_amount(self, raw: str):
        s = re.sub(r'[^\d.,]', '', raw.strip())
        if not s or len(s) < 2:
            return None
        try:
            # 1.234.567 atau 1.234.567,89
            if re.match(r'^\d{1,3}(\.\d{3})+(,\d{1,2})?$', s):
                return float(s.replace('.', '').replace(',', '.'))
            # 1,234,567
            if re.match(r'^\d{1,3}(,\d{3})+(\.\d{1,2})?$', s):
                return float(s.replace(',', ''))
            # 12345,89
            if re.match(r'^\d+(,\d{1,2})$', s):
                return float(s.replace(',', '.'))
            # plain
            cleaned = s.replace(',', '').replace('.', '')
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    def _line_has_noise_pattern(self, line: str) -> bool:
        for pat in NOISE_PATTERNS:
            if re.search(pat, line, re.IGNORECASE):
                return True
        return False

    def _should_skip_line(self, line_lower: str) -> bool:
        return any(kw in line_lower for kw in SKIP_LINE_KEYWORDS)

    def extract_from_image(self, image_bytes: bytes) -> dict:
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = self.preprocess_image(image)

            text_full = pytesseract.image_to_string(
                image,
                lang='ind+eng',
                config='--oem 3 --psm 6'
            )
            logger.debug(f"OCR raw text:\n{text_full}")

            lines = text_full.splitlines()
            total_amount = None
            fallback_amounts = []
            total_keyword_line = None

            for line in lines:
                line_lower = line.lower().strip()

                if not line_lower:
                    continue

                # Skip baris noise berdasarkan keyword
                if self._should_skip_line(line_lower):
                    continue

                # Skip baris yang mengandung pola noise (nomor telp, barcode)
                if self._line_has_noise_pattern(line):
                    continue

                # Cari semua angka di baris ini
                numbers = re.findall(
                    r'\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?\b|\b\d{4,9}\b',
                    line
                )
                parsed = [self.parse_amount(n) for n in numbers]
                # Filter: minimal Rp 500, maksimal Rp 50 juta (hindari barcode)
                valid = [a for a in parsed if a and 500 <= a <= 50_000_000]

                if not valid:
                    continue

                candidate = max(valid)

                # Cek apakah baris ini keyword total — dari yang paling spesifik
                matched_kw = None
                for kw in TOTAL_KEYWORDS:
                    if kw in line_lower:
                        matched_kw = kw
                        break

                if matched_kw:
                    # Prioritas: keyword lebih spesifik (index lebih kecil di list) menang
                    kw_priority = TOTAL_KEYWORDS.index(matched_kw)
                    if total_keyword_line is None or kw_priority < total_keyword_line[0]:
                        total_amount = candidate
                        total_keyword_line = (kw_priority, candidate)
                        logger.debug(f"TOTAL [{matched_kw}]: {candidate} <- '{line.strip()}'")
                    elif kw_priority == total_keyword_line[0] and candidate > total_amount:
                        # Keyword sama, ambil yang lebih besar
                        total_amount = candidate
                        logger.debug(f"TOTAL update [{matched_kw}]: {candidate} <- '{line.strip()}'")
                else:
                    fallback_amounts.append(candidate)

            # Fallback: tidak ada keyword total
            if total_amount is None and fallback_amounts:
                fallback_amounts.sort(reverse=True)
                # Lewati angka terbesar pertama (sering harga satuan tertinggi / kode)
                total_amount = fallback_amounts[min(1, len(fallback_amounts) - 1)]
                logger.debug(f"Fallback amount: {total_amount}")

            return {
                'text': text_full.strip(),
                'amounts': fallback_amounts,
                'largest_amount': total_amount or 0,
                'date': self._extract_date(text_full),
                'description': self._extract_merchant(lines),
            }

        except Exception as e:
            logger.error(f"OCR error: {e}", exc_info=True)
            return {
                'text': '', 'amounts': [], 'largest_amount': 0,
                'date': '-', 'description': 'Struk'
            }

    def _extract_date(self, text: str) -> str:
        patterns = [
            r'\b(\d{2}-\d{2}-\d{4})\b',          # 29-05-2026
            r'\b(\d{2}/\d{2}/\d{4})\b',           # 21/09/2025
            r'\b(\d{4}-\d{2}-\d{2})\b',           # 2026-05-29
            r'\b(\d{1,2}\s+\w+\s+\d{4})\b',       # 29 Mei 2026
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return '-'

    def _extract_merchant(self, lines: list) -> str:
        """
        Ambil nama merchant: cari baris teks murni (tanpa angka dominan)
        di 8 baris pertama, skip baris sangat pendek atau penuh simbol.
        """
        skip_words = [
            'jl.', 'jalan', 'kec.', 'kel.', 'kota', 'no.',
            'telp', 'hp', 'fax', 'bandung', 'jakarta',
            'reff', 'date', 'tanggal', 'kasir', 'server',
            'dine', 'tipe', 'pelanggan', 'loyalty',
        ]
        for line in lines[:10]:
            s = line.strip()
            if len(s) < 4:
                continue
            # Skip jika mayoritas angka
            digit_ratio = sum(c.isdigit() for c in s) / max(len(s), 1)
            if digit_ratio > 0.4:
                continue
            # Skip jika mengandung kata alamat/operasional
            if any(kw in s.lower() for kw in skip_words):
                continue
            # Skip simbol berlebihan
            symbol_ratio = sum(not c.isalnum() and c not in ' -.' for c in s) / max(len(s), 1)
            if symbol_ratio > 0.3:
                continue
            return s[:40]
        return 'Struk'