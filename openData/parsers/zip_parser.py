import os
import zipfile
from .csv_parser import parse_csv
from .xlsx_parser import parse_xlsx
from .txt_parser import parse_txt
from .xml_parser import parse_xml
from .shp_parser import parse_shp
from .base import download_file, HAS_PANDAS, HAS_GEOPANDAS

import json

def parse_zip(url: str, filepath: str) -> tuple:
    """Download and parse ZIP containing any supported data files"""
    download_file(url, filepath)
    records = []

    # Extract ZIP
    extract_dir = filepath.replace('.zip', '_extracted')
    os.makedirs(extract_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        # Collect files by extension
        file_map = {
            'csv': [],
            'xlsx': [],
            'xls': [],
            'txt': [],
            'xml': [],
            'json': [],
            'shp': [],
            'geojson': []
        }

        for root, _, files in os.walk(extract_dir):
            for f in files:
                ext = f.split('.')[-1].lower()
                if ext in file_map:
                    file_map[ext].append(os.path.join(root, f))

        # Priority order: CSV > XLSX/XLS > JSON > XML > TXT > SHP > GEOJSON
        # Will parse the first file of each type found
        if file_map['csv'] and HAS_PANDAS:
            records, _ = parse_csv(file_map['csv'][0], file_map['csv'][0])

        elif (file_map['xlsx'] or file_map['xls']) and HAS_PANDAS:
            if file_map['xlsx']:
                records, _ = parse_xlsx(file_map['xlsx'][0], file_map['xlsx'][0])
            else:
                # use same XLSX parser for xls (it handles engine='xlrd')
                records, _ = parse_xlsx(file_map['xls'][0], file_map['xls'][0])

        elif file_map['json']:
            with open(file_map['json'][0], 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                # Try common keys
                records = data.get('data', data.get('records', [data]))

        elif file_map['xml']:
            records, _ = parse_xml(file_map['xml'][0], file_map['xml'][0])

        elif file_map['txt']:
            records, _ = parse_txt(file_map['txt'][0], file_map['txt'][0])

        elif file_map['shp'] and HAS_GEOPANDAS:
            records, _ = parse_shp(file_map['shp'][0], file_map['shp'][0])

        elif file_map['geojson'] and HAS_GEOPANDAS:
            from .shp_parser import parse_shp
            records, _ = parse_shp(file_map['geojson'][0], file_map['geojson'][0])

        if records:
            print(f"         (parsed {len(records)} records from ZIP)")

    except Exception as e:
        print(f"      ⚠️  ZIP parse error: {e}")

    return records, filepath
