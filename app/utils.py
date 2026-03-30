import re
from typing import Dict, Any

def parse_transaction(text: str) -> Dict[str, Any]:
    text_lower = text.lower().strip()
    
    if not text_lower:
        raise ValueError("Input kosong")

    # ======================
    # AMOUNT (Enhanced parsing)
    # ======================
    amount = None

    # 1. Format ribuan: 25k, 25rb, 25ribu
    k_matches = re.finditer(r'(\d+(?:[.,]\d+)?)\s*(k|rb|ribu)', text_lower)
    for match in k_matches:
        num = float(match.group(1).replace(',', '.'))
        amount = num * 1000
        break

    # 2. Format juta: 3jt, 3juta
    if amount is None:
        jt_matches = re.finditer(r'(\d+(?:[.,]\d+)?)\s*(jt|juta)', text_lower)
        for match in jt_matches:
            num = float(match.group(1).replace(',', '.'))
            amount = num * 1_000_000
            break

    # 3. Angka biasa: 25000, 25.000, 25,000
    if amount is None:
        num_matches = re.findall(r'\b(\d{1,3}(?:[.,]\d{3})*|(?:\d+[.,])?\d+)\b', text_lower)
        for match in num_matches:
            cleaned = re.sub(r'[^\d]', '', match.replace(',', ''))
            try:
                num = float(cleaned)
                if num > 0:
                    amount = num
                    break
            except ValueError:
                continue

    if amount is None:
        raise ValueError("Nominal tidak ditemukan. Contoh: 25rb, 3jt, 25000")

    # ======================
    # TYPE
    # ======================
    income_keywords = ['gaji', 'income', 'gajian', 'masuk', 'transfer masuk', 'bonus']
    expense_keywords = ['bayar', 'beli', 'transfer', 'kirim']
    
    if any(keyword in text_lower for keyword in income_keywords):
        trans_type = 'Pemasukan'
    else:
        trans_type = 'Pengeluaran'

    # ======================
    # CATEGORY (Enhanced)
    # ======================
    food_keywords = ['makan', 'jajan', 'bakso', 'kopi', 'minum', 'mcd', 'kfc', 'warung']
    transport_keywords = ['bensin', 'gojek', 'grab', 'taxi', 'bus', 'ojol']
    shopping_keywords = ['belanja', 'baju', 'sepatu', 'tas']
    
    if any(kw in text_lower for kw in food_keywords):
        category = 'Makanan'
    elif any(kw in text_lower for kw in transport_keywords):
        category = 'Transport'
    elif any(kw in text_lower for kw in shopping_keywords):
        category = 'Belanja'
    else:
        category = 'Lainnya'

    return {
        "amount": round(amount, 2),
        "type": trans_type,
        "category": category,
        "description": text[:100].strip()
    }