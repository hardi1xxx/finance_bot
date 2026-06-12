import io
import re
import json
import base64
import logging
import anthropic

logger = logging.getLogger(__name__)


class OCRProcessor:
    def __init__(self):
        self.client = anthropic.Anthropic()

    def extract_from_image(self, image_bytes: bytes) -> dict:
        try:
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')

            # Deteksi format gambar
            header = image_bytes[:12]
            if header[:3] == b'\xff\xd8\xff':
                media_type = 'image/jpeg'
            elif header[:8] == b'\x89PNG\r\n\x1a\n':
                media_type = 'image/png'
            elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
                media_type = 'image/webp'
            else:
                media_type = 'image/jpeg'  # default

            response = self.client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=500,
                messages=[{
                    'role': 'user',
                    'content': [
                        {
                            'type': 'image',
                            'source': {
                                'type': 'base64',
                                'media_type': media_type,
                                'data': image_b64,
                            }
                        },
                        {
                            'type': 'text',
                            'text': (
                                'Ini adalah foto struk belanja Indonesia. '
                                'Ekstrak informasi berikut dan jawab HANYA dalam format JSON:\n'
                                '{\n'
                                '  "merchant": "nama toko/restoran",\n'
                                '  "total": 127000,\n'
                                '  "date": "29-05-2026"\n'
                                '}\n\n'
                                'Aturan:\n'
                                '- "total" adalah Grand Total / Total Bayar / jumlah akhir yang dibayar (angka bulat tanpa titik/koma)\n'
                                '- Jangan ambil harga satuan item, subtotal sebelum pajak, atau nominal kembalian\n'
                                '- "date" format DD-MM-YYYY, atau "-" jika tidak ada\n'
                                '- "merchant" nama toko saja, bukan alamat\n'
                                '- Jawab JSON saja, tanpa penjelasan apapun'
                            )
                        }
                    ]
                }]
            )

            raw = response.content[0].text.strip()
            # Bersihkan markdown code block jika ada
            raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.MULTILINE).strip()
            data = json.loads(raw)

            # Parse total — hapus semua titik/koma ribuan
            raw_total = str(data.get('total', 0))
            total = float(re.sub(r'[.,]', '', raw_total))

            return {
                'largest_amount': total,
                'description': data.get('merchant', 'Struk'),
                'date': data.get('date', '-'),
                'text': raw,
                'amounts': [total],
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e} | raw: {raw if 'raw' in dir() else 'N/A'}")
            return self._empty_result()

        except Exception as e:
            logger.error(f"Claude OCR error: {e}", exc_info=True)
            return self._empty_result()

    def _empty_result(self) -> dict:
        return {
            'largest_amount': 0,
            'description': 'Struk',
            'date': '-',
            'text': '',
            'amounts': [],
        }