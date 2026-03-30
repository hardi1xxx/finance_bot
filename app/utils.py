import re
from datetime import datetime
from typing import Dict, List, Tuple

def parse_amount(text: str) -> List[Tuple[str, float]]:
    """Extract amounts from text"""
    patterns = [
        r'Rp[.\s]*(\d+[.,]?\d*)',
        r'(\d+[.,]\d{2,3})',
        r'Total[:\s]*(\d+[.,]?\d*)',
        r'(\d{1,3}(?:\.\d{3})*(?:,\d+)?)'
    ]
    
    amounts = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                # Handle different formats: 1.234.567,00 or 1234567.00
                amount = match.replace('.', '').replace(',', '.')
                amounts.append((match, float(amount)))
            except:
                continue
    
    return amounts[:5]  # Max 5 amounts

def parse_date(text: str) -> str:
    """Extract date from text"""
    patterns = [
        r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',
        r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|Mei|Jun|Jul|Agu|Sep|Okt|Nov|Des)[a-z]*\s+\d{4})\b'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return datetime.now().strftime('%d/%m/%Y')

def categorize_transaction(description: str) -> str:
    """Auto categorize transaction"""
    desc = description.lower()
    categories = {
        'makanan': ['makan', 'resto', 'food', 'mcd', 'kfc', 'warung', 'cafe'],
        'transportasi': ['gojek', 'grab', 'ojol', 'bensin', 'spbu', 'pertamina'],
        'belanja': ['indomaret', 'alfamart', 'minimarket', 'toko', 'market'],
        'tagihan': ['pln', 'pdam', 'listrik', 'air', 'internet', 'telkom'],
        'gaji': ['gaji', 'salary', 'transfer masuk', 'pemasukan'],
        'investasi': ['reksadana', 'saham', 'crypto', 'emas']
    }
    
    for category, keywords in categories.items():
        if any(keyword in desc for keyword in keywords):
            return category.title()
    return 'Lainnya'