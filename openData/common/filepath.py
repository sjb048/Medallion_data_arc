import os
import re
from typing import List, Dict, Any, Tuple, Optional
from common.mapping import FIELD_MAP, BOOLEAN_FIELDS, NULL_VALUES
# Import format utilities (re-export for convenience)
from .file_format import (
    FORMAT_PRIORITY,

)
# =============================================================================
# FILE PATH HELPERS
# =============================================================================

def get_raw_filepath(save_folder: str, filename: str) -> str:
    """
    Get filepath for raw downloaded files.
    
    Args:
        save_folder: Base save folder (e.g., "./data_policy_issues")
        filename: Filename with extension (e.g., "dinesafe.csv")
        
    Returns:
        Full path: "./data_policy_issues/raw/dinesafe.csv"
    """
    raw_dir = os.path.join(save_folder, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    return os.path.join(raw_dir, filename)


def get_json_filepath(save_folder: str, filename: str) -> str:
    """
    Get filepath for tagged JSON files.
    
    Args:
        save_folder: Base save folder (e.g., "./data_policy_issues")
        filename: Filename (with or without .json extension)
        
    Returns:
        Full path: "./data_policy_issues/raw/dinesafe.json"
    """
    # print(f"Getting JSON filepath...{save_folder}, {filename}")
    json_dir = os.path.join(save_folder, "json")
    os.makedirs(json_dir, exist_ok=True)
    
    # Ensure .json extension
    if not filename.endswith('.json'):
        filename = f"{filename}.json"
    
    return os.path.join(json_dir, filename)


def get_logs_filepath(save_folder: str, filename: str) -> str:
    """
    Get filepath for log files.
    
    Args:
        save_folder: Base save folder
        filename: Log filename
        
    Returns:
        Full path to log file
    """
    logs_dir = os.path.join(save_folder, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, filename)

def ensure_directories(save_folder: str) -> Dict[str, str]:
    """
    Create all required directories and return their paths.
    
    Args:
        save_folder: Base save folder
        
    Returns:
        Dict with paths: {"raw": "...", "json": "...", "logs": "..."}
    """
    dirs = {
        "raw": os.path.join(save_folder, "raw"),
        "json": os.path.join(save_folder, "json"),
        "logs": os.path.join(save_folder, "logs"),
    }
    
    for path in dirs.values():
        os.makedirs(path, exist_ok=True)
    
    return dirs

# =============================================================================
# FILENAME HELPERS
# =============================================================================



def clean_filename(name: str, max_length: int = 100) -> str:
    """Create safe, slug-like filename."""
    safe = re.sub(r'[^\w\s-]', '', name)
    safe = re.sub(r'[-\s]+', '_', safe)
    safe = safe.strip('_').lower()
    return safe[:max_length]

# def clean_filename(name: str) -> str:
#     """Safe filename"""
#     safe = re.sub(r'[^\w\s-]', '', name)
#     # Replace spaces and multiple dashes/underscores
#     safe = re.sub(r'[-\s]+', '_', safe)
#     return safe.strip('_').lower()

def normalize_record(self, record: Dict) -> Dict:
        """
        Normalize a single record without storing.
        
        Useful for transformations in other pipelines.
        
        Args:
            record: Raw record
            
        Returns:
            Normalized record
        """
        normalized = {}
        
        for key, value in record.items():
            if key == "_id":
                normalized["original_id"] = value
                continue
            
            if key.startswith("_"):
                continue
            
            norm_key = self.field_map.get(key, self._to_snake_case(key))
            norm_value = self._normalize_value(norm_key, value)
            normalized[norm_key] = norm_value
        
        return normalized
    
def _normalize_value(self, field: str, value: Any) -> Any:
        """Normalize a value based on field type."""
        
        # Handle None
        if value is None:
            return None
        
        # Handle strings
        if isinstance(value, str):
            value = value.strip()
            
            # Check for null values
            if value.lower() in NULL_VALUES:
                return None
            
            # Boolean fields
            if field in BOOLEAN_FIELDS:
                return value.upper() in ("Y", "YES", "TRUE", "1", "ACTIVE")
        
        # Boolean conversion for non-strings
        if field in BOOLEAN_FIELDS:
            return bool(value)
        
        return value
    
def _to_snake_case(self, name: str) -> str:
        """Convert field name to snake_case."""
        # Replace common separators
        name = name.replace("-", "_").replace(" ", "_")
        
        # Handle camelCase
        name = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
        
        # Clean up multiple underscores
        name = re.sub(r'_+', '_', name)
        
        return name.lower().strip("_")

def get_filename_from_url(url, format_type):
    """
    Extract a meaningful filename from the URL.
    Falls back to parliament_votes if nothing found.
    
    Args:
        url (str): The URL to extract filename from
        format_type (str): File extension (csv, json, xml)
    
    Returns:
        str: Generated filename with extension
    
    Examples:
        >>> get_filename_from_url('https://example.com/members/en/votes/csv', 'csv')
        'votes.csv'
        >>> get_filename_from_url('https://example.com/data/parliament_2024.csv', 'csv')
        'parliament_2024.csv'
    """
    try:
        # Parse the URL
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        if not path:
            return f"parliament_votes.{format_type}"
        
        # Split path into parts
        parts = path.split('/')
        
        # Get the last part of the path
        last_part = parts[-1] if parts else ''
        
        # Case 1: URL ends with format type (e.g., /votes/csv)
        if last_part.lower() == format_type:
            # Use the second-to-last part if available
            if len(parts) >= 2:
                return f"{parts[-2]}.{format_type}"
            return f"data.{format_type}"
        
        # Case 2: Last part has a file extension
        if '.' in last_part:
            base_name = last_part.rsplit('.', 1)[0]
            return f"{base_name.lower()}.{format_type}"
        
        # Case 3: Last part is meaningful (not just numbers or format type)
        if last_part and not last_part.isdigit():
            return f"{last_part.lower()}.{format_type}"
        
        # Case 4: Build filename from path
        # Remove common prefixes and build meaningful name
        cleaned_parts = []
        skip_prefixes = {'members', 'api', 'data', 'export', 'en', 'fr'}
        
        for part in parts:
            part_lower = part.lower()
            # Skip common prefixes and format types
            if part_lower not in skip_prefixes and part_lower != format_type:
                # Keep meaningful parts (not just numbers)
                if not part.isdigit() or len(cleaned_parts) > 0:
                    cleaned_parts.append(part_lower)
  
        if cleaned_parts:
            # Join with underscore, limit to last 3 parts for readability
            filename_base = '_'.join(cleaned_parts[-3:])
            # filename_base = sanitize_filename(filename_base)
            return f"{filename_base.lower()}.{format_type}"
        
    except Exception as e:
        print(f'  ✗ Error extracting filename: {type(e).__name__}: {str(e)}')
        return f"parliament_votes.{format_type}"


def download_file(url, format_type, output_dir, config):
    """Download a single file."""
    try:
        headers = {'User-Agent': config['user_agent']}
        response = requests.get(url, timeout=config['timeout'], headers=headers)
        
        if response.status_code == 200:
            filename = get_filename_from_url(url, format_type)
            print(f'  ✓ Successfully downloaded filename: {filename} ({len(response.content):,} bytes)')
            filepath = os.path.join(output_dir, filename)
            
            if file_exists_prompt(filepath):
                print(f'  ⚠ File exists, replacing: {filepath}')
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            # print(f'  ✓ Successfully downloaded: {filepath} ({len(response.content):,} bytes)')
            return True
        
        elif response.status_code == 403:
            print(f'  ✗ Access forbidden (403) - may need authentication')
        elif response.status_code == 404:
            print(f'  ✗ Not found (404) - URL may be incorrect')
        else:
            print(f'  ✗ Download failed: Status {response.status_code}')
        
        return False
    
    except requests.exceptions.Timeout:
        print(f'  ✗ Error: Request timed out')
        return False
    except Exception as e:
        print(f'  ✗ Error downloading: {type(e).__name__}: {str(e)[:100]}')
        return False

# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

__all__ = [
    # File paths
    'get_raw_filepath',
    'get_json_filepath',
    'get_logs_filepath',
    'ensure_directories',
    
    # Filename helpers
    'clean_filename'
]