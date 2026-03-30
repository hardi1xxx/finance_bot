import re

def parse_transaction(text: str):
    text_lower = text.lower()

    # ===== AMOUNT =====
    if 'k' in text_lower or 'rb' in text_lower:
        num = re.sub(r'[^\d]', '', text_lower)
        amount = float(num) * 1000
    elif 'jt' in text_lower:
        num = re.sub(r'[^\d]', '', text_lower)
        amount = float(num) * 1_000_000
    else:
        cleaned = re.sub(r'[^\d,\.]', '', text_lower)
        cleaned = cleaned.replace('.', '').replace(',', '.')
        amount = float(cleaned)

    # ===== TYPE =====
    if any(x in text_lower for x in ['gaji', 'income', 'masuk']):
        trans_type = 'Pemasukan'
    else:
        trans_type = 'Pengeluaran'

    # ===== CATEGORY =====
    if any(x in text_lower for x in ['makan', 'bakso', 'kopi']):
        category = 'Makanan'
    elif any(x in text_lower for x in ['bensin', 'gojek']):
        category = 'Transport'
    else:
        category = 'Lainnya'

    return {
        "amount": amount,
        "type": trans_type,
        "category": category,
        "description": text
    }