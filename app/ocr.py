import io
import re
import json
import base64
import logging
import os
import anthropic

logger = logging.getLogger(__name__)


class OCRProcessor:
    def __init__(self):
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY tidak ditemukan di environment!")
        logger.info(f"OCR init: API key found, starts with {api_key[:15]}...")
        self.client = anthropic.Anthropic(api_key=api_key)

    def extract_from_image(self, image_bytes: bytes) -> dict:
        raw = ''
        error_detail = ''
        try:
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')

            header = image_bytes[:12]
            if header[:3] == b'\xff\xd8\xff':
                media_type = 'image/jpeg'
            elif header[:8] == b'\x89PNG\r\n\x1a\n':
                media_type = 'image/png'
            elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
                media_type = 'image/webp'
            else:
                media_type = 'image/jpeg'

            logger.info(f"OCR: media_type={media_type}, size={len(image_bytes)} bytes")

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
            logger.info(f"OCR raw response: {raw}")

            raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.MULTILINE).strip()
            data = json.loads(raw)

            raw_total = str(data.get('total', 0))
            total = float(re.sub(r'[^\d]', '', raw_total) or '0')

            logger.info(f"OCR result: merchant={data.get('merchant')}, total={total}, date={data.get('date')}")

            return {
                'largest_amount': total,
                'description': data.get('merchant', 'Struk'),
                'date': data.get('date', '-'),
                'text': raw,
                'amounts': [total],
                'error': '',
            }

        except anthropic.AuthenticationError as e:
            error_detail = f'Auth error: {str(e)[:100]}'
            logger.error(error_detail)

        except anthropic.APIConnectionError as e:
            error_detail = f'Connection error: {str(e)[:100]}'
            logger.error(error_detail)

        except anthropic.BadRequestError as e:
            error_detail = f'Bad request: {str(e)[:100]}'
            logger.error(error_detail)

        except json.JSONDecodeError as e:
            error_detail = f'JSON error: {e} | raw: {raw[:100]}'
            logger.error(error_detail)

        except Exception as e:
            error_detail = f'{type(e).__name__}: {str(e)[:100]}'
            logger.error(f"Claude OCR error: {e}", exc_info=True)

        result = self._empty_result()
        result['error'] = error_detail
        return result

    def _empty_result(self) -> dict:
        return {
            'largest_amount': 0,
            'description': 'Struk',
            'date': '-',
            'text': '',
            'amounts': [],
            'error': '',
        }