def categorize_transaction(desc: str) -> str:
    desc = desc.lower()

    if any(x in desc for x in ['makan', 'kopi', 'resto']):
        return 'Makanan'
    elif any(x in desc for x in ['bensin', 'transport']):
        return 'Transport'
    elif any(x in desc for x in ['gaji', 'salary']):
        return 'Pemasukan'
    else:
        return 'Lainnya'