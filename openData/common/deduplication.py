# deduplication.py
"""
Resource Deduplication

Handle duplicate resources in datasets (same data in multiple formats).

Usage:
    from deduplication import (
        deduplicate_resources,
        normalize_resource_name,
        categorize_resources,
    )
    
    # Remove duplicates, keep best format
    unique = deduplicate_resources(resources)
"""

import re
from typing import List, Dict, Any, Optional

try:
    from .file_format import get_format_priority
except ImportError:
    try:
        from file_format import get_format_priority
    except ImportError:
        # Fallback if file_format not available
        def get_format_priority(fmt: str, has_datastore: bool = False) -> int:
            if has_datastore:
                return 0
            priority_map = {
                'json': 1, 'csv': 2, 'xlsx': 3, 'xls': 4,
                'xml': 5, 'txt': 6, 'zip': 7, 'shp': 8
            }
            return priority_map.get(fmt.lower(), 99)


# =============================================================================
# NAME NORMALIZATION
# =============================================================================

# Format suffixes to remove during normalization
FORMAT_SUFFIXES = [
    # File extensions
    '.csv', '.json', '.xml', '.xlsx', '.xls', '.txt', '.zip', '.shp', '.geojson',
    # Format mentions with separators
    ' - csv', ' - json', ' - xml', ' - xlsx',
    ' csv', ' json', ' xml', ' xlsx',
    '_csv', '_json', '_xml', '_xlsx',
    '-csv', '-json', '-xml', '-xlsx',
]

# Parenthetical format mentions
FORMAT_PARENS_PATTERN = re.compile(r'\s*\((csv|json|xml|xlsx|xls|txt|zip|shp)\)', re.IGNORECASE)

# Pattern to detect year/version suffixes that should be PRESERVED
YEAR_PATTERN = re.compile(r'[_\-\s]?((?:19|20)\d{2})(?:[_\-\s]|$)', re.IGNORECASE)
VERSION_PATTERN = re.compile(r'[_\-\s]?v?\d+(?:\.\d+)?(?:[_\-\s]|$)', re.IGNORECASE)



def normalize_resource_name(name: str, fmt: str = None) -> str:
    """
    Normalize resource name for deduplication comparison.
    
    Removes format suffixes, extensions, and normalizes for comparison.
    
    Args:
        name: Resource name
        fmt: Optional format (unused, kept for compatibility)
        
    Returns:
        Normalized name for comparison
        
    Examples:
        "DineSafe - CSV" → "dinesafe"
        "data.json" → "data"
        "Beach Water Quality (XML)" → "beach water quality"
        "inspections_2024_csv" → "inspections_2024"
    """
    if not name:
        return ""
    
    name_lower = name.lower().strip()
    
    # Remove file extensions
    for suffix in FORMAT_SUFFIXES:
        if name_lower.endswith(suffix):
            name_lower = name_lower[:-len(suffix)]
    
    # Remove format mentions in parentheses
    name_lower = FORMAT_PARENS_PATTERN.sub('', name_lower)
    
    return name_lower.strip()

def extract_base_name_for_grouping(name: str) -> str:
    """
    Extract base name for grouping, REMOVING year/version info.
    
    This is used to identify potential duplicates that might be
    the same data in different formats.
    
    Args:
        name: Normalized resource name
        
    Returns:
        Base name without year/version
        
    Examples:
        "ob_report_2016" → "ob_report"
        "inspections_v2" → "inspections"
    """
    base = name
    
    # Remove year patterns
    base = YEAR_PATTERN.sub('', base)
    
    # Remove version patterns
    base = VERSION_PATTERN.sub('', base)
    
    # Clean up trailing underscores/dashes
    base = re.sub(r'[_\-]+$', '', base)
    
    return base.strip()

def get_resource_signature(resource: Dict[str, Any]) -> str:
    """
    Create a signature that identifies unique data sources.
    
    Two resources are considered duplicates only if they have:
    - Same signature (name + URL-based identifier)
    - Different formats
    
    This handles cases where:
    1. Resources have different names (e.g., ob_report_2016, ob_report_2017)
    2. Resources have SAME name but different URLs (common in Toronto Open Data)
    
    Args:
        resource: Resource dictionary
        
    Returns:
        Signature string for grouping
    """
    name = resource.get("name", "")
    normalized = normalize_resource_name(name)
    url = resource.get("url", "")
    
    # Extract year/version from URL if not in name
    url_identifier = ""
    if url:
        # Look for year in URL (e.g., ob_report_2016.json)
        year_match = YEAR_PATTERN.search(url)
        if year_match:
            url_identifier = year_match.group(1)
        else:
            # Use filename from URL as identifier
            import os
            filename = os.path.basename(url.split('?')[0])  # Remove query params
            filename_norm = normalize_resource_name(filename)
            if filename_norm and filename_norm != normalized:
                url_identifier = filename_norm
    
    # Check if year is already in the normalized name
    name_has_year = bool(YEAR_PATTERN.search(normalized))
    
    # Build signature
    if url_identifier and not name_has_year:
        # Name doesn't have year but URL does - include URL identifier
        signature = f"{normalized}:{url_identifier}"
    else:
        # Name already has year or no URL identifier found
        signature = normalized
    
    return signature if signature else resource.get("id", "unknown")


def names_match(name1: str, name2: str) -> bool:
    """
    Check if two resource names refer to the same data.
    
    Args:
        name1: First resource name
        name2: Second resource name
        
    Returns:
        True if names match after normalization
    """
    norm1 = normalize_resource_name(name1)
    norm2 = normalize_resource_name(name2)
    return norm1 == norm2

def are_format_duplicates(resource1: Dict, resource2: Dict) -> bool:
    """
    Check if two resources are the same data in different formats.
    
    Only returns True if resources have:
    - Same normalized name (including year/version)
    - Different formats (e.g., one is CSV, other is JSON)
    
    Args:
        resource1: First resource
        resource2: Second resource
        
    Returns:
        True if they're duplicates (same data, different format)
    """
    name1 = normalize_resource_name(resource1.get("name", ""))
    name2 = normalize_resource_name(resource2.get("name", ""))
    
    # Names must match exactly (including year/version)
    if name1 != name2:
        return False
    
    # Formats must be different
    fmt1 = resource1.get("format", "").lower()
    fmt2 = resource2.get("format", "").lower()
    
    return fmt1 != fmt2

# =============================================================================
# DEDUPLICATION
# =============================================================================

def deduplicate_resources(
    resources: List[Dict[str, Any]],
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    Remove duplicate resources, keeping the best format for each unique resource.
    
    Some datasets have the same data in multiple formats (CSV, JSON, XML).
    This keeps only the highest-priority format for each unique resource.
    
    Args:
        resources: List of resource dictionaries from CKAN API
        verbose: Print info about duplicates found
        
    Returns:
        Deduplicated list of resources
        
    Example:
        If a dataset has:
        - "ob_report_2016" (JSON)
        - "ob_report_2016" (CSV)    → These are duplicates, keep JSON
        - "ob_report_2017" (JSON)   → This is separate, KEEP IT!
        - "ob_report_2018" (JSON)   → This is separate, KEEP IT!

    """
    if not resources:
        return []
    
    # Group by normalized name
    resource_groups: Dict[str, List[Dict]] = {}
    
    for resource in resources:
        # Get signature that PRESERVES year/version info
        signature = get_resource_signature(resource)
        
        if signature not in resource_groups:
            resource_groups[signature] = []
        resource_groups[signature].append(resource)
    
    
    # Select best from each group
    unique_resources = []
    
    for signature, group in resource_groups.items():
        if len(group) == 1:
            unique_resources.append(group[0])
        else:
            # Multiple resources with same signature
            # These are true format duplicates - pick the best one
            group.sort(key=_get_resource_sort_key)
            best = group[0]
            unique_resources.append(best)
            
            if verbose:
                skipped = [r.get("format", "?") for r in group[1:]]
                best_fmt = "DATASTORE" if best.get("datastore_active") else best.get("format", "?").upper()
                print(f"    ℹ️  '{best.get('name')}' - using {best_fmt}, skipping {skipped}")
    
    if verbose:
        print(f"    📊 Deduplication: {len(resources)} resources → {len(unique_resources)} unique")
    
    return unique_resources


def _get_resource_sort_key(resource: Dict[str, Any]) -> int:
    """Get sort key for resource priority."""
    has_datastore = resource.get("datastore_active", False)
    fmt = resource.get("format", "").lower()
    return get_format_priority(fmt, has_datastore)


# =============================================================================
# CATEGORIZATION
# =============================================================================

def categorize_resources(resources: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
    """
    Categorize resources by format type.
    
    Useful for understanding what formats are available in a dataset.
    
    Args:
        resources: List of resource dictionaries
        
    Returns:
        Dict with categorized resources:
        {
            "datastore": [...],  # Can use datastore API
            "json": [...],       # Direct JSON files
            "csv": [...],        # CSV files
            "geo": [...],        # Geospatial (SHP, GeoJSON)
            "excel": [...],      # Excel files
            "other": [...]       # XML, TXT, ZIP, etc.
        }
    """
    categorized = {
        "datastore": [],
        "json": [],
        "csv": [],
        "geo": [],
        "excel": [],
        "other": []
    }
    
    for r in resources:
        fmt = r.get("format", "").lower()
        url = r.get("url", "").lower()
        name = r.get("name", "").lower()
        
        if not r.get("url"):
            continue
        
        if r.get("datastore_active"):
            categorized["datastore"].append(r)
        elif fmt in ("json",) or url.endswith('.json'):
            categorized["json"].append(r)
        elif fmt == "csv" or url.endswith('.csv'):
            categorized["csv"].append(r)
        elif fmt in ("shp", "shapefile", "geojson") or \
             url.endswith(('.shp', '.geojson')) or \
             any(x in name for x in ["shapefile", "shape", "geo"]):
            categorized["geo"].append(r)
        elif fmt in ("xlsx", "xls") or url.endswith(('.xlsx', '.xls')):
            categorized["excel"].append(r)
        else:
            categorized["other"].append(r)
    
    return categorized


def group_by_name(resources: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
    """
    Group resources by normalized name.
    
    Useful for seeing which resources have multiple formats.
    
    Args:
        resources: List of resource dictionaries
        
    Returns:
        Dict mapping normalized names to list of resources
    """
    groups: Dict[str, List[Dict]] = {}
    
    for resource in resources:
        name = resource.get("name", "")
        base_name = normalize_resource_name(name)
        
        if not base_name:
            base_name = resource.get("id", "unknown")
        
        if base_name not in groups:
            groups[base_name] = []
        groups[base_name].append(resource)
    
    return groups

def group_by_base_name(resources: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
    """
    Group resources by base name (without year/version).
    
    Useful for seeing all versions of the same data.
    
    Args:
        resources: List of resource dictionaries
        
    Returns:
        Dict mapping base names to list of resources
    """
    groups: Dict[str, List[Dict]] = {}
    
    for resource in resources:
        name = resource.get("name", "")
        normalized = normalize_resource_name(name)
        base_name = extract_base_name_for_grouping(normalized)
        
        if not base_name:
            base_name = resource.get("id", "unknown")
        
        if base_name not in groups:
            groups[base_name] = []
        groups[base_name].append(resource)
    
    return groups


def find_duplicates(resources: List[Dict[str, Any]]) -> List[Dict[str, List[Dict]]]:
    """
    Find resources that have duplicates (multiple formats).
    
    Args:
        resources: List of resource dictionaries
        
    Returns:
        List of groups that have more than one format
    """
    groups = group_by_name(resources)
    
    duplicates = []
    for name, group in groups.items():
        if len(group) > 1:
            duplicates.append({
                "name": name,
                "formats": [r.get("format", "?") for r in group],
                "resources": group
            })
    
    return duplicates


def get_duplicate_summary(resources: List[Dict[str, Any]]) -> str:
    """
    Get a human-readable summary of duplicates.
    
    Args:
        resources: List of resource dictionaries
        
    Returns:
        Summary string
    """
    duplicates = find_duplicates(resources)
    
    if not duplicates:
        return "No duplicates found"
    
    lines = [f"Found {len(duplicates)} resource(s) with multiple formats:"]
    for dup in duplicates:
        lines.append(f"  - '{dup['name']}': {', '.join(dup['formats'])}")
    
    return "\n".join(lines)

def get_yearly_resources_summary(resources: List[Dict[str, Any]]) -> str:
    """
    Get a summary of resources grouped by year/version.
    
    Args:
        resources: List of resource dictionaries
        
    Returns:
        Summary string showing yearly breakdown
    """
    groups = group_by_base_name(resources)
    
    lines = ["Resource groups by base name:"]
    for base_name, group in sorted(groups.items()):
        names = [r.get("name", "?") for r in group]
        lines.append(f"  {base_name}:")
        for name in names:
            lines.append(f"    - {name}")
    
    return "\n".join(lines)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Name normalization
    'normalize_resource_name',
    'names_match',
    'extract_base_name_for_grouping',
    'get_resource_signature',
    'are_format_duplicates',
    
    # Deduplication
    'deduplicate_resources',
    
    # Categorization
    'categorize_resources',
    'group_by_name',
    'group_by_base_name',
    
    # Analysis
    'find_duplicates',
    'get_duplicate_summary',
    'get_yearly_resources_summary',
]
