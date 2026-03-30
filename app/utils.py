import re

def parse_transaction(text: str):
    text_lower = text.lower().strip()

    # ======================
    # AMOUNT (FIX ALL FORMAT)
    # ======================
    amount = None

    # format: 25k / 25rb
    match_k = re.search(r'(\d+)\s*(k|rb)', text_lower)
    if match_k:
        amount = float(match_k.group(1)) * 1000

    # format: 3jt
    match_jt = re.search(r'(\d+)\s*(jt)', text_lower)
    if match_jt:
        amount = float(match_jt.group(1)) * 1_000_000

    # format angka biasa: 10000 / 10.000 / 10,000
    if amount is None:
        cleaned = re.sub(r'[^\d,\.]', '', text_lower)

        if cleaned:
            cleaned = cleaned.replace('.', '').replace(',', '.')
            amount = float(cleaned)

    # kalau tetap gagal
    if amount is None:
        raise ValueError("Nominal tidak ditemukan")

    # ======================
    # TYPE
    # ======================
    if any(x in text_lower for x in ['gaji', 'income', 'masuk']):
        trans_type = 'Pemasukan'
    else:
        trans_type = 'Pengeluaran'

    # ======================
    # CATEGORY
    # ======================
    if any(x in text_lower for x in ['makan', 'jajan', 'bakso', 'kopi']):
        category = 'Makanan'
    elif any(x in text_lower for x in ['bensin', 'gojek', 'transport']):
        category = 'Transport'
    else:
        category = 'Lainnya'

    return {
        "amount": amount,
        "type": trans_type,
        "category": category,
        "description": text
    }