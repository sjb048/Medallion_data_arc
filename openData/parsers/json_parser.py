# parsers/json_parser.py
"""
JSON/GeoJSON Parser

Downloads and parses JSON files from URLs.

Usage:
    from parsers.json_parser import parse_json, parse_json_file
    
    # From URL (downloads and saves raw)
    records, raw_path = parse_json(url, raw_filepath)
    
    # From local file
    records = parse_json_file(filepath)
"""

import os
import json
import requests
from typing import List, Dict, Any, Tuple, Optional


def parse_json(url: str, raw_filepath: str, timeout: int = 60) -> Tuple[List[Dict], str]:
    """
    Download JSON from URL, save raw file, and parse to records.
    
    Args:
        url: URL to download from
        raw_filepath: Path to save raw JSON file
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (records list, raw_filepath)
        
    Example:
        records, path = parse_json(
            "https://example.com/data.json",
            "./raw/data.json"
        )
    """
    # Download
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(raw_filepath), exist_ok=True)
    
    # Save raw
    with open(raw_filepath, 'wb') as f:
        f.write(response.content)
    
    # Parse
    data = response.json()
    records = extract_records(data)
    
    return records, raw_filepath


def parse_json_file(filepath: str) -> List[Dict]:
    """
    Parse JSON from local file.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        List of records
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return extract_records(data)


def extract_records(data: Any) -> List[Dict]:
    """
    Extract records from various JSON structures.
    
    Handles:
    - Plain array: [record1, record2, ...]
    - GeoJSON: {"type": "FeatureCollection", "features": [...]}
    - Wrapped: {"records": [...]} or {"data": [...]}
    - CKAN result: {"result": {"records": [...]}}
    - Single object: {"field": "value"} → [{"field": "value"}]
    
    Args:
        data: Parsed JSON data
        
    Returns:
        List of record dictionaries
    """
    if data is None:
        return []
    
    # Already a list
    if isinstance(data, list):
        return data
    
    # Dict with various structures
    if isinstance(data, dict):
        # GeoJSON FeatureCollection
        if data.get('type') == 'FeatureCollection' and 'features' in data:
            return _flatten_geojson_features(data['features'])
        
        # GeoJSON features array (without type check)
        if 'features' in data and isinstance(data['features'], list):
            return _flatten_geojson_features(data['features'])
        
        # Common wrapper keys (in priority order)
        for key in ['records', 'data', 'items', 'results', 'rows', 'values']:
            if key in data and isinstance(data[key], list):
                return data[key]
        
        # CKAN API result structure
        if 'result' in data:
            result = data['result']
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                for key in ['records', 'data', 'items']:
                    if key in result and isinstance(result[key], list):
                        return result[key]
        
        # Success/response wrapper
        if 'success' in data and 'result' not in data:
            # Check other keys for the actual data
            for key, value in data.items():
                if key not in ['success', 'help', 'error'] and isinstance(value, list):
                    return value
        
        # Single object - wrap in list
        return [data]
    
    return []


def _flatten_geojson_features(features: List[Dict]) -> List[Dict]:
    """
    Flatten GeoJSON features by merging properties with geometry.
    
    GeoJSON structure:
        {"type": "Feature", "properties": {...}, "geometry": {...}}
    
    Becomes:
        {"type": "Feature", "geometry": {...}, "prop1": val1, ...}
    
    Args:
        features: List of GeoJSON features
        
    Returns:
        List of flattened records
    """
    records = []
    
    for feature in features:
        if not isinstance(feature, dict):
            continue
        
        record = {}
        
        # Flatten properties to top level
        properties = feature.get('properties', {})
        if properties:
            record.update(properties)
        
        # Keep geometry
        if 'geometry' in feature:
            record['geometry'] = feature['geometry']
        
        # Keep feature type and id if present
        if 'type' in feature:
            record['_feature_type'] = feature['type']
        if 'id' in feature:
            record['_feature_id'] = feature['id']
        
        records.append(record)
    
    return records


def is_geojson(data: Any) -> bool:
    """Check if data is GeoJSON."""
    if not isinstance(data, dict):
        return False
    
    return (
        data.get('type') == 'FeatureCollection' or
        data.get('type') == 'Feature' or
        'features' in data
    )


def get_json_structure(data: Any) -> str:
    """
    Identify JSON structure type for debugging.
    
    Returns one of:
    - 'array': Plain array
    - 'geojson': GeoJSON FeatureCollection
    - 'records': {"records": [...]}
    - 'data': {"data": [...]}
    - 'ckan': CKAN API response
    - 'object': Single object
    - 'unknown': Unrecognized structure
    """
    if isinstance(data, list):
        return 'array'
    
    if isinstance(data, dict):
        if is_geojson(data):
            return 'geojson'
        if 'records' in data:
            return 'records'
        if 'data' in data:
            return 'data'
        if 'result' in data:
            return 'ckan'
        return 'object'
    
    return 'unknown'


# =============================================================================
# EXPORTS
# =============================================================================

# __all__ = [
#     'parse_json',
#     'parse_json_file',
#     'extract_records',
#     'is_geojson',
#     'get_json_structure',
# ]