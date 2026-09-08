
"""
Field Name Mapping & Normalization

Centralizes all field mappings for Bronze → Silver transformation.

Usage:
    from field_mapping import (
        FIELD_MAP,
        normalize_field_name,
        normalize_value,
        normalize_record,
    )
    
    # Normalize a field name
    norm_name = normalize_field_name("Institution Name")  # → "institution_name"
    
    # Normalize a complete record
    normalized = normalize_record(raw_record)
"""

import re
from typing import Dict, Any, Optional


# =============================================================================
# FIELD NORMALIZATIONS (for Silver layer)
# =============================================================================

FIELD_MAP = {
    # Outbreak data
    "Institution Name": "institution_name",
    "Institution Address": "institution_address",
    "Outbreak Setting": "outbreak_setting",
    "Type of Outbreak": "outbreak_type",
    "Causative Agent-1": "causative_agent_1",
    "Causative Agent-2": "causative_agent_2",
    "Date Outbreak Began": "date_outbreak_began",
    "Date Declared Over": "date_declared_over",
    "Active": "is_active",
    
     # ─────────────────────────────────────────────────────────────────────────
    # DINESAFE / BODYSAFE (Health Inspections)
    # ─────────────────────────────────────────────────────────────────────────
    "Establishment Name": "establishment_name",
    "Establishment Address": "establishment_address",
    "Establishment Type": "establishment_type",
    "Establishment Status": "establishment_status",
    "Inspection Date": "inspection_date",
    "Infraction Details": "infraction_details",
    "Severity": "severity",
    "Action": "action",
    "Court Outcome": "court_outcome",
    "Amount Fined": "amount_fined",

    # ─────────────────────────────────────────────────────────────────────────
    # BEACH WATER QUALITY
    # ─────────────────────────────────────────────────────────────────────────
    "Beach Name": "beach_name",
    "Beach ID": "beach_id",
    "Sample Date": "sample_date",
    "E.Coli Level": "ecoli_level",
    "Beach Status": "beach_status",
    "Beach Advisory": "beach_advisory",

    # ─────────────────────────────────────────────────────────────────────────
    # HOUSING / APARTMENTS / CONDOS
    # ─────────────────────────────────────────────────────────────────────────
    "Property Type": "property_type",
    "Property Address": "property_address",
    "Building Name": "building_name",
    "Street Name": "street_name",
    "Street No": "street_no",
    "Street Number": "street_number",
    "Unit Number": "unit_number",
    "Postal Code": "postal_code",
    "Ward": "ward",
    "Ward Name": "ward_name",
    "Neighbourhood": "neighbourhood",
    "Year Built": "year_built",
    "Year Registered": "year_registered",
    "Number of Storeys": "num_storeys",
    "Number of Units": "num_units",
    "Confirmed Storeys": "confirmed_storeys",
    "Confirmed Units": "confirmed_units",
    
    # Common fields
    "Address": "address",
    "Postal Code": "postal_code",
    "Ward": "ward",

    # ─────────────────────────────────────────────────────────────────────────
    # COMMON FIELDS
    # ─────────────────────────────────────────────────────────────────────────
    "Address": "address",
    "Full Address": "full_address",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "Lat": "latitude",
    "Lon": "longitude",
    "Long": "longitude",
    "Location": "location",
    "Comments": "comments",
    "Description": "description",
    "Name": "name",
    "ID": "id",
    "Status": "status",
    "Date": "date",
    "Created Date": "created_date",
    "Modified Date": "modified_date",
    "Last Updated": "last_updated",
}

# =============================================================================
# BOOLEAN FIELDS (convert Y/N, Yes/No, True/False → true/false)
# =============================================================================

BOOLEAN_FIELDS = {
    "is_active",
    "is_open",
    "is_closed",
    "active",
    "approved",
    "verified",
}

# =============================================================================
# NULL-EQUIVALENT VALUES (convert to null)
# =============================================================================

NULL_VALUES = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    # "unable to identify",
    # "not available",
    # "not applicable",
    # "unknown",
    "-",
    "--",
    ".",
}


def parse_boolean(value: Any) -> Optional[bool]:
    """
    Parse various boolean representations.
    
    Args:
        value: Value to parse
        
    Returns:
        True, False, or None
    """
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        val_lower = value.lower().strip()
        
        if val_lower in ("y", "yes", "true", "1", "active", "open"):
            return True
        if val_lower in ("n", "no", "false", "0", "inactive", "closed"):
            return False
    
    if isinstance(value, (int, float)):
        return bool(value)
    
    return None

def add_field_mapping(original: str, normalized: str):
    """
    Add a new field mapping at runtime.
    
    Args:
        original: Original field name
        normalized: Normalized field name
        
    Example:
        add_field_mapping("My Custom Field", "my_custom_field")
    """
    FIELD_MAP[original] = normalized


def get_all_mappings() -> Dict[str, str]:
    """Get a copy of all field mappings."""
    return FIELD_MAP.copy()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Constants
    'FIELD_MAP',
    'BOOLEAN_FIELDS',
    'NULL_VALUES',
    

    'parse_boolean',
    # 'normalize_record',
    'add_field_mapping',
    'get_all_mappings',
]
