#!/usr/bin/env python3
"""
Dynamic Elasticsearch Mapping Generator

Scans JSON files to auto-detect fields and generate appropriate ES mappings.
Handles unknown/variable data structures.

Usage:
    python generate_es_mapping.py /path/to/json/folder
    python generate_es_mapping.py /path/to/json/folder --output my_mapping.py
    python generate_es_mapping.py /path/to/single_file.json
"""

import json
import re
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Set, List, Tuple
from collections import defaultdict


class FieldTypeDetector:
    """Detect field types from sample values."""
    
    # Date patterns to check
    DATE_PATTERNS = [
        r'^\d{4}-\d{2}-\d{2}$',                    # 2019-12-31
        r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',  # ISO format
        r'^\d{2}/\d{2}/\d{4}$',                    # 12/31/2019
        r'^\d{4}/\d{2}/\d{2}$',                    # 2019/12/31
        r'^\d{2}-\d{2}-\d{4}$',                    # 31-12-2019
    ]
    
    # Keywords that suggest specific types
    DATE_KEYWORDS = ['date', 'time', 'created', 'updated', 'timestamp', 'began', 'ended', 'over']
    GEO_KEYWORDS = ['lat', 'lng', 'longitude', 'latitude', 'location', 'geometry', 'coordinates']
    ID_KEYWORDS = ['id', '_id', 'code', 'number', 'no', 'num']
    
    @classmethod
    def detect_type(cls, field_name: str, values: List[Any]) -> Tuple[str, dict]:
        """
        Detect ES field type from field name and sample values.
        
        Returns:
            Tuple of (es_type, mapping_config)
        """
        field_lower = field_name.lower()
        
        # Filter out None/empty values for analysis
        non_empty_values = [v for v in values if v is not None and v != '']
        
        if not non_empty_values:
            return 'keyword', {'type': 'keyword'}
        
        sample = non_empty_values[:100]  # Analyze first 100 values
        
        # Check for geo fields
        if any(kw in field_lower for kw in cls.GEO_KEYWORDS):
            if cls._is_geo_point(sample):
                return 'geo_point', {'type': 'geo_point', 'ignore_malformed': True}
            if cls._is_geo_shape(sample):
                return 'geo_shape', {'type': 'geo_shape', 'ignore_malformed': True}
        
        # Check for date fields
        if any(kw in field_lower for kw in cls.DATE_KEYWORDS) or cls._looks_like_date(sample):
            return 'date', {
                'type': 'date',
                'format': 'yyyy-MM-dd||yyyy-MM-dd\'T\'HH:mm:ss||epoch_millis||strict_date_optional_time',
                'ignore_malformed': True
            }
        
        # Check value types
        value_types = set(type(v).__name__ for v in sample)
        
        # All integers
        if value_types <= {'int'}:
            return 'long', {'type': 'long'}
        
        # All floats or mix of int/float
        if value_types <= {'int', 'float'}:
            return 'float', {'type': 'float'}
        
        # Boolean
        if value_types <= {'bool'}:
            return 'boolean', {'type': 'boolean'}
        
        # Lists/arrays
        if 'list' in value_types:
            # Analyze list contents
            flat_values = []
            for v in sample:
                if isinstance(v, list):
                    flat_values.extend(v)
            if flat_values:
                inner_type, _ = cls.detect_type(field_name, flat_values)
                if inner_type == 'text':
                    return 'keyword', {'type': 'keyword'}  # Arrays of strings → keyword
            return 'keyword', {'type': 'keyword'}
        
        # Dicts (nested objects)
        if 'dict' in value_types:
            return 'object', {'type': 'object', 'enabled': True}
        
        # String analysis
        if value_types <= {'str', 'int', 'float'}:
            str_values = [str(v) for v in sample if v]
            
            # Check if it's an ID/code field (short, alphanumeric)
            if any(kw in field_lower for kw in cls.ID_KEYWORDS):
                return 'keyword', {'type': 'keyword'}
            
            # Check average length
            avg_len = sum(len(s) for s in str_values) / len(str_values) if str_values else 0
            unique_ratio = len(set(str_values)) / len(str_values) if str_values else 0
            
            # Short values with high uniqueness → keyword
            if avg_len < 50 and unique_ratio > 0.8:
                return 'keyword', {'type': 'keyword'}
            
            # Short values, low uniqueness (categories) → keyword
            if avg_len < 100 and unique_ratio < 0.1:
                return 'keyword', {'type': 'keyword'}
            
            # Long text → text with keyword subfield
            return 'text', {
                'type': 'text',
                'fields': {
                    'keyword': {'type': 'keyword', 'ignore_above': 256}
                }
            }
        
        # Default
        return 'keyword', {'type': 'keyword'}
    
    @classmethod
    def _looks_like_date(cls, values: List[Any]) -> bool:
        """Check if values look like dates."""
        str_values = [str(v) for v in values if v][:20]
        if not str_values:
            return False
        
        matches = 0
        for val in str_values:
            for pattern in cls.DATE_PATTERNS:
                if re.match(pattern, val):
                    matches += 1
                    break
        
        return matches / len(str_values) > 0.5
    
    @classmethod
    def _is_geo_point(cls, values: List[Any]) -> bool:
        """Check if values are geo points."""
        for v in values[:5]:
            if isinstance(v, dict) and 'lat' in v and 'lon' in v:
                return True
            if isinstance(v, list) and len(v) == 2:
                if all(isinstance(x, (int, float)) for x in v):
                    return True
        return False
    
    @classmethod
    def _is_geo_shape(cls, values: List[Any]) -> bool:
        """Check if values are GeoJSON shapes."""
        for v in values[:5]:
            if isinstance(v, dict) and 'type' in v and 'coordinates' in v:
                return True
        return False


class MappingGenerator:
    """Generate Elasticsearch mappings from JSON data."""
    
    def __init__(self):
        self.field_values = defaultdict(list)  # field_name → [values]
        self.field_sources = defaultdict(set)  # field_name → {source_files}
        self.files_scanned = 0
        self.records_scanned = 0
    
    def scan_file(self, filepath: str) -> dict:
        """Scan a single JSON file and collect field information."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        filename = os.path.basename(filepath)
        
        # Handle tagged format with _metadata and records
        if isinstance(data, dict) and 'records' in data:
            records = data['records']
            metadata = data.get('_metadata', {})
        elif isinstance(data, list):
            records = data
            metadata = {}
        elif isinstance(data, dict):
            records = [data]
            metadata = {}
        else:
            return {'error': f'Unknown format in {filepath}'}
        
        self.files_scanned += 1
        
        for record in records:
            self.records_scanned += 1
            self._collect_fields(record, filename)
        
        return {
            'file': filename,
            'records': len(records),
            'fields': len(set(self.field_values.keys()))
        }
    
    def _collect_fields(self, record: dict, source: str, prefix: str = ''):
        """Recursively collect field names and values."""
        if not isinstance(record, dict):
            return
        
        for key, value in record.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            self.field_values[full_key].append(value)
            self.field_sources[full_key].add(source)
            
            # Recurse into nested objects (but not too deep)
            if isinstance(value, dict) and prefix.count('.') < 2:
                self._collect_fields(value, source, full_key)
    
    def scan_directory(self, directory: str) -> List[dict]:
        """Scan all JSON files in a directory."""
        results = []
        path = Path(directory)
        
        for json_file in path.glob('*.json'):
            try:
                result = self.scan_file(str(json_file))
                results.append(result)
                print(f"  ✓ Scanned {json_file.name}: {result.get('records', 0)} records")
            except Exception as e:
                print(f"  ✗ Error scanning {json_file.name}: {e}")
                results.append({'file': json_file.name, 'error': str(e)})
        
        return results
    
    def generate_mapping(self, index_name: str = 'my_index') -> dict:
        """Generate Elasticsearch mapping from collected field data."""
        properties = {}
        
        # Always include standard fields
        standard_fields = {
            'doc_id': {'type': 'keyword'},
            '_unique_id': {'type': 'keyword'},
            'dataset_id': {'type': 'keyword'},
            'dataset_name': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
            'primary_issue': {'type': 'keyword'},
            'secondary_issues': {'type': 'keyword'},
            'subcategory': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
            'data_type': {'type': 'keyword'},
            'issue_keywords': {'type': 'keyword'},
            'searchable_text': {
                'type': 'text',
                'analyzer': 'standard',
                'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}
            },
            'source': {'type': 'keyword'},
            'source_collection': {'type': 'keyword'},
            'loaded_at': {'type': 'date'},
            '@timestamp': {'type': 'date'},
        }
        properties.update(standard_fields)
        
        # Generate mappings for discovered fields
        for field_name, values in self.field_values.items():
            # Skip internal fields
            if field_name.startswith('_') and field_name not in ['_id']:
                continue
            
            # Normalize field name for ES
            es_field_name = self._normalize_field_name(field_name)
            
            # Skip if already in standard fields
            if es_field_name in properties:
                continue
            
            # Detect type
            _, mapping = FieldTypeDetector.detect_type(field_name, values)
            properties[es_field_name] = mapping
        
        return {
            'settings': {
                'number_of_shards': 1,
                'number_of_replicas': 0,
                'analysis': {
                    'analyzer': {
                        'custom_analyzer': {
                            'type': 'custom',
                            'tokenizer': 'standard',
                            'filter': ['lowercase', 'stop', 'snowball']
                        }
                    }
                }
            },
            'mappings': {
                'properties': properties,
                'dynamic_templates': [
                    {
                        'strings_as_keywords': {
                            'match_mapping_type': 'string',
                            'mapping': {
                                'type': 'text',
                                'fields': {
                                    'keyword': {'type': 'keyword', 'ignore_above': 256}
                                }
                            }
                        }
                    }
                ]
            }
        }
    
    def generate_field_map(self) -> dict:
        """Generate a FIELD_MAP for normalizing field names."""
        field_map = {}
        
        for original_name in self.field_values.keys():
            normalized = self._normalize_field_name(original_name)
            if normalized != original_name:
                field_map[original_name] = normalized
        
        return field_map
    
    def _normalize_field_name(self, name: str) -> str:
        """Normalize field name for Elasticsearch."""
        # Replace spaces and special chars
        normalized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Convert to snake_case
        normalized = re.sub(r'([a-z])([A-Z])', r'\1_\2', normalized)
        normalized = normalized.lower()
        # Remove multiple underscores
        normalized = re.sub(r'_+', '_', normalized)
        # Remove leading/trailing underscores
        normalized = normalized.strip('_')
        return normalized
    
    def get_field_report(self) -> str:
        """Generate a human-readable field report."""
        lines = [
            "=" * 70,
            "FIELD ANALYSIS REPORT",
            "=" * 70,
            f"Files scanned: {self.files_scanned}",
            f"Records scanned: {self.records_scanned}",
            f"Unique fields found: {len(self.field_values)}",
            "",
            "-" * 70,
            f"{'Field Name':<40} {'Type':<15} {'Sources'}",
            "-" * 70,
        ]
        
        for field_name in sorted(self.field_values.keys()):
            values = self.field_values[field_name]
            sources = self.field_sources[field_name]
            
            es_type, _ = FieldTypeDetector.detect_type(field_name, values)
            
            lines.append(f"{field_name[:40]:<40} {es_type:<15} {len(sources)} files")
        
        lines.append("=" * 70)
        return '\n'.join(lines)


def save_mapping_file(mapping: dict, field_map: dict, output_path: str, index_name: str):
    """Save mapping as a Python module."""
    content = f'''# Auto-generated Elasticsearch mapping
# Generated: {datetime.now().isoformat()}
# Index: {index_name}

{index_name.upper()}_MAPPING = {json.dumps(mapping, indent=4)}

# Field name normalization map (original → normalized)
FIELD_MAP = {json.dumps(field_map, indent=4)}
'''
    
    with open(output_path, 'w') as f:
        f.write(content)
    
    print(f"\n✅ Saved mapping to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate ES mapping from JSON files')
    parser.add_argument('path', help='Path to JSON file or directory')
    parser.add_argument('--output', '-o', default='generated_mapping.py', help='Output file')
    parser.add_argument('--index', '-i', default='my_index', help='Index name')
    parser.add_argument('--report', '-r', action='store_true', help='Show field report')
    
    args = parser.parse_args()
    
    generator = MappingGenerator()
    path = Path(args.path)
    
    print(f"\n🔍 Scanning: {args.path}\n")
    
    if path.is_file():
        generator.scan_file(str(path))
    elif path.is_dir():
        generator.scan_directory(str(path))
    else:
        print(f"Error: Path not found: {args.path}")
        sys.exit(1)
    
    # Show report
    if args.report:
        print(generator.get_field_report())
    
    # Generate mapping
    mapping = generator.generate_mapping(args.index)
    field_map = generator.generate_field_map()
    
    # Save
    save_mapping_file(mapping, field_map, args.output, args.index)
    
    print(f"\n📊 Summary:")
    print(f"   Files scanned:    {generator.files_scanned}")
    print(f"   Records scanned:  {generator.records_scanned}")
    print(f"   Fields detected:  {len(generator.field_values)}")
    print(f"   Mapping fields:   {len(mapping['mappings']['properties'])}")


if __name__ == '__main__':
    main()