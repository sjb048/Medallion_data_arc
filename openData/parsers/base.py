import os
import requests
import re
from typing import List, Dict
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False

def download_file(url: str, filepath: str) -> str:
    """Download file from URL to specified filepath"""
    response = requests.get(url)
    response.raise_for_status()
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'wb') as f:
        f.write(response.content)
    return filepath

def normalize_col(col: str) -> str:
    if not col:
        return ""
    col = str(col)
    # Remove .0 from float years like "2020.0" -> "2020"
    if re.match(r'^\d+\.0$', col):
        col = col.replace('.0', '')
    # Replace problematic characters for MongoDB
    col = col.replace(' ', '_')
    col = col.replace('-', '_')
    col = col.replace('.', '_')  # MongoDB doesn't allow dots in field names
    col = col.replace('$', '_')  # MongoDB doesn't allow $ in field names
    col = col.replace('/', '_')
    col = col.replace('\\', '_')
    col = re.sub(r'_+', '_', col)  # Collapse multiple underscores
    col = col.strip('_').lower()
    return col


def sanitize_field_names_for_mongodb(records: List[Dict]) -> List[Dict]:
    """
    Sanitize field names for MongoDB compatibility.
    
    MongoDB doesn't allow:
    - Field names starting with '$'
    - Field names containing '.'
    
    This function replaces problematic characters with underscores.
    """
    if not records:
        return records
    
    sanitized_records = []
    for record in records:
        sanitized = {}
        for key, value in record.items():
            # Replace dots with underscores (MongoDB treats dots as nested paths)
            new_key = str(key).replace('.', '_')
            # Replace $ with underscore ($ is reserved in MongoDB)
            new_key = new_key.replace('$', '_')
            # Remove leading underscores if they're not intentional
            while new_key.startswith('__'):
                new_key = new_key[1:]
            sanitized[new_key] = value
        sanitized_records.append(sanitized)
    
    return sanitized_records
