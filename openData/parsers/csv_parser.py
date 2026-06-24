from .base import download_file, HAS_PANDAS

if HAS_PANDAS:
    import pandas as pd


def parse_csv(url: str, filepath: str) -> tuple:

    download_file(url, filepath)
    records = []

    if not HAS_PANDAS:
        print("⚠️ pandas not installed")
        return [], filepath
    
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-16']

    for enc in encodings:
        try:
            df = pd.read_csv(filepath, encoding=enc)
            records = df.to_dict(orient='records')
            print(f"parsed CSV with {enc}")
            break
        except:
            continue
        
    if not records:
        try:
            df = pd.read_csv(filepath, encoding='latin-1', on_bad_lines='skip')
            records = df.to_dict(orient='records')
        except Exception as e:
            print(f"CSV parse failed: {e}")
    return records, filepath