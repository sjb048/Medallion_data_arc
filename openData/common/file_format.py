# file_format.py
"""
File Format Detection & Priority

Handles format detection, priority scoring, and download method selection.

Usage:
    from file_format import (
        get_resource_priority,
        get_format_priority,
        is_supported_format,
        FORMAT_PRIORITY,
    )
    
    # Get download method for a resource
    method, fmt = get_resource_priority(resource)
    
    # Check if format is supported
    if is_supported_format(resource):
        ...
"""

from typing import Dict, Any, Tuple, Optional, List


# =============================================================================
# FORMAT PRIORITY
# =============================================================================

# Priority score (lower = better)
FORMAT_PRIORITY = {
    "datastore": 0,   # Best - clean JSON via API
    "json": 1,        # Native JSON
    "geojson": 2,     # GeoJSON
    "csv": 3,         # CSV - widely supported
    "xlsx": 4,        # Excel (newer)
    "xls": 5,         # Excel (older)
    "xml": 6,         # XML
    "txt": 7,         # Text (tab/comma delimited)
    "zip": 8,         # ZIP archive
    "shp": 9,         # Shapefile
}

# Supported formats set
SUPPORTED_FORMATS = set(FORMAT_PRIORITY.keys())

# Geo-related keywords for detecting geospatial ZIPs
GEO_KEYWORDS = [
    "shapefile", "shp", "geo", "boundary", "wgs84", "map",
    "polygon", "point", "line", "spatial", "gis", "geometry",
    "coordinate", "lat", "lon", "shape"
]

# File extensions that indicate direct download (not reliable datastore)
DIRECT_DOWNLOAD_EXTENSIONS = ['.xlsx', '.xls', '.csv', '.json', '.geojson', '.xml', '.txt', '.zip', '.shp']

# =============================================================================
# FORMAT PRIORITY FUNCTIONS
# =============================================================================
# def _has_direct_download_url(url: str) -> bool:
#     """
#     Check if URL indicates a direct file download.
    
#     These files often have datastore_active=True but datastore doesn't work.
#     """
#     url_lower = url.lower()
#     return any(url_lower.endswith(ext) for ext in DIRECT_DOWNLOAD_EXTENSIONS)

def get_format_priority(fmt: str, has_datastore: bool = False) -> int:
    """
    Get priority score for a format (lower = better).
    
    Args:
        fmt: Format string (e.g., "csv", "json")
        has_datastore: Whether datastore API is available
        
    Returns:
        Priority score (0 = best, 99 = unsupported)
        
    Examples:
        get_format_priority("json") → 1
        get_format_priority("csv") → 3
        get_format_priority("csv", has_datastore=True) → 0
        get_format_priority("unknown") → 99
    """
    if has_datastore:
        return 0
    return FORMAT_PRIORITY.get(fmt.lower(), 99)

def _get_format_from_url(url: str) -> Optional[str]:
    """Extract format from URL extension."""
    url_lower = url.lower()
    
    if url_lower.endswith('.xlsx'):
        return 'xlsx'
    if url_lower.endswith('.xls'):
        return 'xls'
    if url_lower.endswith('.csv'):
        return 'csv'
    if url_lower.endswith('.json'):
        return 'json'
    if url_lower.endswith('.geojson'):
        return 'geojson'
    if url_lower.endswith('.xml'):
        return 'xml'
    if url_lower.endswith('.txt'):
        return 'txt'
    if url_lower.endswith('.zip'):
        return 'zip'
    if url_lower.endswith('.shp'):
        return 'shp'
    
    return None

def get_resource_priority(resource: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Determine the best method and format to download a resource.
    
    Args:
        resource: Resource dictionary from CKAN API
        
    Returns:
        Tuple of (method, format) or (None, None) if unsupported
        
    Methods:
        - "datastore": Fetch via CKAN datastore API
        - "json_file": Download JSON directly
        - "csv": Download and parse CSV
        - "xlsx": Download and parse Excel
        - "xml": Download and parse XML
        - "shp": Download and parse Shapefile
        - "zip": Download and extract ZIP
        - "txt": Download and parse text
        
    Examples:
        # Datastore available
        get_resource_priority({"datastore_active": True, "url": "..."})
        → ("datastore", "json")
        
        # CSV file
        get_resource_priority({"format": "CSV", "url": "http://.../data.csv"})
        → ("csv", "csv")
    """
   
    fmt = resource.get("format", "").lower()
    datastore_active = resource.get("datastore_active", False)
    url = resource.get("url", "").lower()
    name = resource.get("name", "").lower()
    
   
    # No URL = can't download
    if not resource.get("url"):
        return (None, None)
    
   # ═══════════════════════════════════════════════════════════════════════
    # STEP 1: Check URL extension - direct downloads are more reliable
    # ═══════════════════════════════════════════════════════════════════════
    
    url_format = _get_format_from_url(url)
    
    if url_format:
        # URL has explicit file extension - use direct download
        if url_format in ('xlsx', 'xls'):
            return ("xlsx", url_format)
        if url_format == 'csv':
            return ("csv", "csv")
        if url_format == 'json':
            return ("json_file", "json")
        if url_format == 'geojson':
            return ("json_file", "geojson")
        if url_format == 'xml':
            return ("xml", "xml")
        if url_format == 'txt':
            return ("txt", "txt")
        if url_format == 'zip':
            if _is_geo_resource(name, url):
                return ("shp", "zip")
            return ("zip", "zip")
        if url_format == 'shp':
            return ("shp", "shp")
    
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2: No file extension in URL - check datastore
    # ═══════════════════════════════════════════════════════════════════════
    
    # Priority 1: Datastore API (best - returns clean JSON)
    if datastore_active:
        # print(f"Detected datastore format from file format for resource '{name}' with URL '{url}'")
        return ("datastore", "json")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Fall back to format field for remaining cases
    # ═══════════════════════════════════════════════════════════════════════
    
    # Priority 2: Native JSON
    if fmt == "json":
        return ("json_file", "json")
    
    if fmt == "geojson":
        return ("json_file", "geojson")
    
    if fmt == "csv":
        return ("csv", "csv")
    
    if fmt in ("xlsx", "xls"):
        return ("xlsx", fmt)
    
    if fmt == "xml":
        return ("xml", "xml")
    
    if fmt == "txt":
        return ("txt", "txt")
    
    if fmt in ("shp", "shapefile"):
        return ("shp", "shp")
    
    if fmt == "zip":
        if _is_geo_resource(name, url):
            return ("shp", "zip")
        return ("zip", "zip")
    
    return (None, None)

def _is_geo_resource(name: str, url: str) -> bool:
    """
    Check if resource appears to be geospatial data.
    """
    return any(kw in name for kw in GEO_KEYWORDS) or \
           any(kw in url for kw in GEO_KEYWORDS)

def is_supported_format(resource: Dict[str, Any]) -> bool:
    """
    Check if resource format is supported.
    
    Args:
        resource: Resource dictionary from CKAN API
        
    Returns:
        True if we can download/parse this format
    """
    method, _ = get_resource_priority(resource)
    return method is not None



# =============================================================================
# FORMAT DETECTION HELPERS
# =============================================================================

def detect_format_from_url(url: str) -> Optional[str]:
    """
    Detect format from URL extension.
    
    Args:
        url: Resource URL
        
    Returns:
        Format string or None
        
    Examples:
        detect_format_from_url("http://.../data.csv") → "csv"
        detect_format_from_url("http://.../file.json") → "json"
    """
    url_lower = url.lower()
    
    extensions = {
        '.json': 'json',
        '.geojson': 'geojson',
        '.csv': 'csv',
        '.xlsx': 'xlsx',
        '.xls': 'xls',
        '.xml': 'xml',
        '.txt': 'txt',
        '.zip': 'zip',
        '.shp': 'shp',
    }
    
    for ext, fmt in extensions.items():
        if url_lower.endswith(ext):
            return fmt
    
    return None


def detect_format(resource: Dict[str, Any]) -> Optional[str]:
    """
    Detect format from resource metadata or URL.
    
    Args:
        resource: Resource dictionary
        
    Returns:
        Format string or None
    """
    # First check explicit format
    fmt = resource.get("format", "").lower()
    if fmt in SUPPORTED_FORMATS:
        return fmt
    
    # Fall back to URL detection
    url = resource.get("url", "")
    if url:
        return detect_format_from_url(url)
    
    return None


def get_file_extension(fmt: str) -> str:
    """
    Get file extension for a format.
    
    Args:
        fmt: Format string
        
    Returns:
        Extension with dot (e.g., ".csv")
    """
    extensions = {
        'json': '.json',
        'geojson': '.geojson',
        'csv': '.csv',
        'xlsx': '.xlsx',
        'xls': '.xls',
        'xml': '.xml',
        'txt': '.txt',
        'zip': '.zip',
        'shp': '.shp',
    }
    return extensions.get(fmt.lower(), '')


# =============================================================================
# RESOURCE SORTING & FILTERING
# =============================================================================

def sort_by_priority(resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort resources by format priority (best first).
    
    Args:
        resources: List of resource dictionaries
        
    Returns:
        Sorted list (best formats first)
    """
    def get_priority(r):
        has_datastore = r.get("datastore_active", False)
        fmt = r.get("format", "").lower()
        return get_format_priority(fmt, has_datastore)
    
    return sorted(resources, key=get_priority)


def filter_supported(resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter to only supported formats.
    
    Args:
        resources: List of resource dictionaries
        
    Returns:
        List with only supported formats
    """
    return [r for r in resources if is_supported_format(r)]


def get_best_resource(resources: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Get the best (highest priority) resource from a list.
    
    Args:
        resources: List of resource dictionaries
        
    Returns:
        Best resource or None if empty/no supported formats
    """
    supported = filter_supported(resources)
    if not supported:
        return None
    
    sorted_resources = sort_by_priority(supported)
    return sorted_resources[0]


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Constants
    'FORMAT_PRIORITY',
    'SUPPORTED_FORMATS',
    'GEO_KEYWORDS',
    
    # Priority functions
    'get_format_priority',
    'get_resource_priority',
    'is_supported_format',
    
    # Detection helpers
    'detect_format',
    'detect_format_from_url',
    'get_file_extension',
    
    # Sorting & filtering
    'sort_by_priority',
    'filter_supported',
    'get_best_resource',
]