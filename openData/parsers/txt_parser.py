# txt_parser.py
# Text file parser - handles various text formats (TSV, pipe-delimited, fixed-width, etc.)

import os
import re
from .base import download_file, normalize_col, HAS_PANDAS

if HAS_PANDAS:
    import pandas as pd


def detect_delimiter(sample_lines: list) -> str:
    """Detect the most likely delimiter in text data"""
    delimiters = {
        '\t': 0,
        ',': 0,
        '|': 0,
        ';': 0,
    }
    
    for line in sample_lines[:10]:
        for delim in delimiters:
            delimiters[delim] += line.count(delim)
    
    # Return delimiter with highest count (if significant)
    best_delim = max(delimiters, key=delimiters.get)
    if delimiters[best_delim] > len(sample_lines):
        return best_delim
    return None


def parse_txt(url: str, filepath: str, delimiter: str = None) -> tuple:
    """
    Download and parse a text file from URL.
    
    Attempts to detect format:
    - TSV (tab-separated)
    - Pipe-delimited
    - Fixed-width
    - Plain text (returns as single-column records)
    
    Args:
        url: URL to download the text file from
        filepath: Local path to save the file
        delimiter: Force a specific delimiter (auto-detect if None)
        
    Returns:
        Tuple of (records list, filepath)
    """
    download_file(url, filepath)
    records = []
    
    if not HAS_PANDAS:
        print("       ⚠️ pandas not installed, falling back to basic parsing")
        return _parse_txt_basic(filepath)
    
    try:
        # Read file to detect format
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            sample_lines = [f.readline() for _ in range(20)]
        
        # Detect delimiter if not specified
        if delimiter is None:
            delimiter = detect_delimiter(sample_lines)
        
        if delimiter:
            # Delimited file (TSV, CSV-like, pipe, etc.)
            df = pd.read_csv(filepath, sep=delimiter, encoding='utf-8', 
                             on_bad_lines='skip', engine='python')
            
            # Clean column names
            df.columns = [normalize_col(str(col)) for col in df.columns]
            
            # Remove empty columns
            df = df.dropna(axis=1, how='all')
            
            records = df.to_dict(orient='records')
            print(f"       ✅ Parsed delimited text ({len(records)} rows, delimiter='{repr(delimiter)}')")
        else:
            # Try fixed-width format
            try:
                df = pd.read_fwf(filepath, encoding='utf-8')
                df.columns = [normalize_col(str(col)) for col in df.columns]
                df = df.dropna(axis=1, how='all')
                records = df.to_dict(orient='records')
                print(f"       ✅ Parsed fixed-width text ({len(records)} rows)")
            except Exception:
                # Fall back to line-by-line
                records = _parse_txt_lines(filepath)
                
    except Exception as e:
        print(f"       ⚠️ Pandas parsing failed: {e}, falling back to basic parsing")
        records = _parse_txt_lines(filepath)
    
    return records, filepath


def _parse_txt_basic(filepath: str) -> tuple:
    """Basic text parsing without pandas"""
    records = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        if not lines:
            return [], filepath
        
        # Check if first line looks like a header
        first_line = lines[0].strip()
        delimiter = detect_delimiter(lines[:10])
        
        if delimiter:
            # Parse as delimited
            header = [normalize_col(h) for h in first_line.split(delimiter)]
            for line in lines[1:]:
                values = line.strip().split(delimiter)
                if len(values) == len(header):
                    records.append(dict(zip(header, values)))
        else:
            # Return as line records
            for i, line in enumerate(lines):
                records.append({
                    "line_number": i + 1,
                    "content": line.strip()
                })
        
        print(f"       ✅ Parsed text file ({len(records)} records)")
        
    except Exception as e:
        print(f"       ❌ Text parse failed: {e}")
    
    return records, filepath


def _parse_txt_lines(filepath: str) -> list:
    """Parse text file as individual lines"""
    records = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for i, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped:  # Skip empty lines
                    records.append({
                        "line_number": i,
                        "content": stripped
                    })
        print(f"       ✅ Parsed as line records ({len(records)} lines)")
    except Exception as e:
        print(f"       ❌ Text parse failed: {e}")
    
    return records


def parse_txt_from_file(filepath: str, delimiter: str = None) -> list:
    """Parse a text file that's already downloaded"""
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return []
    
    records, _ = parse_txt("", filepath, delimiter)
    return records