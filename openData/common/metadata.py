"""
Metadata Inference Helpers

Uses config/taxonomy.py as the source of truth for issue classification.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime



try:
    from .taxonomy import ISSUE_TAXONOMY, DATASET_ISSUE_MAP
except ImportError:
    # Fallback if config not available
    ISSUE_TAXONOMY = {}
    DATASET_ISSUE_MAP = {}
    print("⚠️  taxonomy.py not found, using empty taxonomy.")


# =============================================================================
# DATA TYPE PATTERNS (not in taxonomy.py, so we keep these)
# =============================================================================

DATA_TYPE_PATTERNS = {
    'inspection': ['inspection', 'audit', 'review', 'check', 'dinesafe', 'bodysafe'],
    'outbreak': ['outbreak', 'epidemic', 'infection', 'communicable'],
    'complaint': ['complaint', 'request', '311', 'service request', 'report'],
    'permit': ['permit', 'license', 'registration', 'application', 'certificate'],
    'incident': ['incident', 'accident', 'collision', 'occurrence', 'event', 'fatal'],
    'measurement': ['measurement', 'reading', 'observation', 'sample', 'monitor', 'quality'],
    'location': ['location', 'facility', 'centre', 'center', 'station', 'site'],
    'inventory': ['inventory', 'list', 'directory', 'catalogue', 'registry'],
    'boundary': ['boundary', 'zone', 'district', 'ward', 'area', 'region'],
    'schedule': ['schedule', 'calendar', 'hours', 'timing'],
    'statistics': ['statistics', 'summary', 'annual', 'report'],
}

# =============================================================================
# ISSUE MAPPING (from taxonomy.py)
# =============================================================================

def get_issue_mapping(package_name: str) -> Optional[Dict[str, Any]]:
    """
    Get explicit issue mapping from DATASET_ISSUE_MAP.
    
    Args:
        package_name: CKAN package name
        
    Returns:
        Mapping dict or None if not found
        
    Example:
        get_issue_mapping("dinesafe")
        → {"primary": "health", "secondary": [], "subcategory": "food_safety"}
    """
    return DATASET_ISSUE_MAP.get(package_name)

def infer_primary_issue(package_name: str, title: str = None) -> Optional[str]:
    """
    Infer primary issue from package name.
    
    1. First checks DATASET_ISSUE_MAP (explicit mapping)
    2. Falls back to keyword matching from ISSUE_TAXONOMY
    
    Args:
        package_name: CKAN package name
        title: Optional package title
        
    Returns:
        Issue category or None
        
    Examples:
        infer_primary_issue("dinesafe") → "health"
        infer_primary_issue("apartment-building-registration") → "housing"
    """
    # 1. Check explicit mapping first (most accurate)
    mapping = DATASET_ISSUE_MAP.get(package_name)
    if mapping:
        return mapping.get("primary")
    
    # 2. Fall back to keyword matching
    text = f"{package_name} {title or ''}".lower()
    
    for issue, config in ISSUE_TAXONOMY.items():
        keywords = config.get("keywords", [])
        if any(kw in text for kw in keywords):
            return issue
    
    return None


def infer_subcategory(package_name: str, primary_issue: str = None) -> Optional[str]:
    """
    Infer subcategory from package name.
    
    1. First checks DATASET_ISSUE_MAP
    2. Falls back to subcategory keyword matching
    
    Args:
        package_name: CKAN package name
        primary_issue: Already inferred primary issue
        
    Returns:
        Subcategory string or None
    """
    # 1. Check explicit mapping
    mapping = DATASET_ISSUE_MAP.get(package_name)
    if mapping:
        return mapping.get("subcategory")
    
    # 2. Fall back to keyword matching within issue's subcategories
    if not primary_issue or primary_issue not in ISSUE_TAXONOMY:
        return None
    
    name_lower = package_name.lower()
    subcategories = ISSUE_TAXONOMY[primary_issue].get("subcategories", {})
    
    for subcat_name, subcat_config in subcategories.items():
        keywords = subcat_config.get("keywords", [])
        if any(kw in name_lower for kw in keywords):
            return subcat_name
    
    return None


def get_secondary_issues(package_name: str) -> List[str]:
    """
    Get secondary issues from DATASET_ISSUE_MAP.
    
    Args:
        package_name: CKAN package name
        
    Returns:
        List of secondary issues
    """
    mapping = DATASET_ISSUE_MAP.get(package_name)
    if mapping:
        return mapping.get("secondary", [])
    return []


def get_issue_keywords(package_name: str, primary_issue: str = None) -> List[str]:
    """
    Get relevant keywords for the dataset's issue.
    
    Args:
        package_name: CKAN package name
        primary_issue: Primary issue category
        
    Returns:
        List of keywords
    """
    keywords = []
    
    if primary_issue and primary_issue in ISSUE_TAXONOMY:
        issue_config = ISSUE_TAXONOMY[primary_issue]
        keywords.extend(issue_config.get("keywords", [])[:10])
        
        # Add subcategory keywords if we can find them
        subcategory = infer_subcategory(package_name, primary_issue)
        if subcategory:
            subcat_config = issue_config.get("subcategories", {}).get(subcategory, {})
            keywords.extend(subcat_config.get("keywords", []))
    
    return list(set(keywords))[:20]  # Dedupe and limit


# =============================================================================
# DATA TYPE INFERENCE
# =============================================================================

def infer_data_type(package_name: str, resource_name: str = None) -> str:
    """
    Infer data type from package/resource name.
    
    Args:
        package_name: CKAN package name
        resource_name: Optional resource name
        
    Returns:
        Data type string
    """
    text = f"{package_name} {resource_name or ''}".lower()
    
    for data_type, keywords in DATA_TYPE_PATTERNS.items():
        if any(kw in text for kw in keywords):
            return data_type
    
    return "record"


# =============================================================================
# METADATA BUILDER
# =============================================================================

def build_metadata(
    package_name: str,
    resource: Dict[str, Any],
    package_info: Dict[str, Any] = None,
    record_count: int = 0,
    extra: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Build complete metadata dict for a dataset.
    
    Uses DATASET_ISSUE_MAP for accurate classification when available.
    
    Args:
        package_name: CKAN package name
        resource: Resource dict from API
        package_info: Optional package metadata
        record_count: Number of records
        extra: Optional extra metadata to merge
        
    Returns:
        Complete metadata dictionary
    """
    resource_name = resource.get("name", "")
    package_title = package_info.get("title", "") if package_info else ""
    package_notes = package_info.get("notes", "") if package_info else ""
    
    # Get taxonomy mapping
    explicit_mapping = get_issue_mapping(package_name)
    
    if explicit_mapping:
        # Use explicit mapping (most accurate)
        primary_issue = explicit_mapping.get("primary")
        secondary_issues = explicit_mapping.get("secondary", [])
        subcategory = explicit_mapping.get("subcategory")
    else:
        # Fall back to inference
        primary_issue = infer_primary_issue(package_name, package_title)
        secondary_issues = []
        subcategory = infer_subcategory(package_name, primary_issue)
    
    metadata = {
        # Identifiers
        "dataset_id": f"{package_name}_{_clean_for_id(resource_name or 'data')}",
        "dataset_name": resource_name or package_name,
        "package_name": package_name,
        "resource_id": resource.get("id"),
        
        # Source info
        "source": "toronto-open-data",
        "source_url": resource.get("url"),
        "format_original": resource.get("format"),
        
        # Timestamps
        "download_date": datetime.now().isoformat(),
        "record_count": record_count,
        
        # Taxonomy (from taxonomy.py or inferred)
        "primary_issue": primary_issue,
        "secondary_issues": secondary_issues,
        "subcategory": subcategory,
        "data_type": infer_data_type(package_name, resource_name),
        "issue_keywords": get_issue_keywords(package_name, primary_issue),
        
        # Package info
        "package_title": package_title[:200] if package_title else None,
        "package_notes": package_notes[:500] if package_notes else None,
    }
    
    # Merge extra metadata (can override inferred values)
    if extra:
        metadata.update(extra)
    
    return metadata


def _clean_for_id(name: str) -> str:
    """Clean a name for use in dataset_id."""
    import re
    clean = re.sub(r'[^\w\s-]', '', name)
    clean = re.sub(r'[-\s]+', '_', clean)
    return clean.strip('_').lower()[:50]


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # From taxonomy.py (re-exported)
    'ISSUE_TAXONOMY',
    'DATASET_ISSUE_MAP',
    
    # Mapping functions
    'get_issue_mapping',
    'infer_primary_issue',
    'infer_subcategory',
    'get_secondary_issues',
    'get_issue_keywords',
    
    # Data type
    'DATA_TYPE_PATTERNS',
    'infer_data_type',
    
    # Builder
    'build_metadata',
]
