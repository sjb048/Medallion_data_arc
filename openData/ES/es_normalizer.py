# elasticsearch/normalizer.py
# Field normalization and searchable text building

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List

from .mapping import ISSUE_SEARCH_FIELDS

# =============================================================================
# FIELD NAME NORMALIZATIONS
# =============================================================================

FIELD_MAP = {
    # =========================================================================
    # ADDRESS VARIATIONS
    # =========================================================================
    "addr_full": "addrFull",
    "address_full": "addrFull",
    "full_address": "addrFull",
    "ADDR_FULL": "addrFull",
    "ADDRESS": "address",
    "Street_Name": "street_name",
    "STREET_NAME": "street_name",
    "Street_No": "street_no",
    "Street_No.": "street_no",
    "STREET_NO": "street_no",
    "Postal_Code": "postal_code",
    "POSTAL_CODE": "postal_code",
    "Ward": "ward",
    "WARD": "ward",
    "Neighbourhood": "neighbourhood",
    "NEIGHBOURHOOD": "neighbourhood",
    
    # =========================================================================
    # HEALTH FIELD VARIATIONS
    # =========================================================================
    # Establishment
    "establishment_name": "estName",
    "est_name": "estName",
    "Establishment_Name": "estName",
    "ESTABLISHMENT_NAME": "estName",
    "Name": "estName",
    "NAME": "estName",
    
    # Inspection
    "inspection_date": "insDate",
    "ins_date": "insDate",
    "Inspection_Date": "insDate",
    "INSPECTION_DATE": "insDate",
    "inspection_status": "insStatus",
    "ins_status": "insStatus",
    "Inspection_Status": "insStatus",
    "INSPECTION_STATUS": "insStatus",
    
    # Infraction
    "infraction_type": "infType",
    "Infraction_Type": "infType",
    "infraction_category": "infCategory",
    "Infraction_Category": "infCategory",
    "deficiency_desc": "defDesc",
    "Deficiency_Description": "defDesc",
    
    # E. coli variations
    "e_coli": "eColi",
    "ecoli": "eColi",
    "E_Coli": "eColi",
    "E.Coli": "eColi",
    "ECOLI": "eColi",
    
    # Beach variations
    "Beach_Name": "beachName",
    "beach_name": "beachName",
    "BEACH_NAME": "beachName",
    "Site_Name": "siteName",
    "site_name": "siteName",
    "SITE_NAME": "siteName",
    "Collection_Date": "collectionDate",
    "collection_date": "collectionDate",
    "COLLECTION_DATE": "collectionDate",
    
    # =========================================================================
    # HOUSING FIELD VARIATIONS
    # =========================================================================
    "Year": "year",
    "YEAR": "year",
    
    # Unit counts
    "Total_Units": "total_units",
    "TOTAL_UNITS": "total_units",
    "Bachelor_Units": "bachelor_units",
    "BACHELOR_UNITS": "bachelor_units",
    "One_Bedroom_Units": "one_bedroom_units",
    "ONE_BEDROOM_UNITS": "one_bedroom_units",
    "Two_Bedroom_Units": "two_bedroom_units",
    "TWO_BEDROOM_UNITS": "two_bedroom_units",
    "Three_+_Bedroom_Units": "three_plus_bedroom_units",
    "Three_Plus_Bedroom_Units": "three_plus_bedroom_units",
    "THREE_PLUS_BEDROOM_UNITS": "three_plus_bedroom_units",
    "Commercial_Units": "commercial_units",
    "COMMERCIAL_UNITS": "commercial_units",
    
    # Percentages
    "Bachelor_Units_Pct": "bachelor_units_pct",
    "One_Bedroom_Units_Pct": "one_bedroom_units_pct",
    "Two_Bedroom_Units_Pct": "two_bedroom_units_pct",
    "Three_+_Bedroom_Units_Pct": "three_plus_bedroom_units_pct",
    "Three_Plus_Bedroom_Units_Pct": "three_plus_bedroom_units_pct",
    
    # Registration
    "Date_of_Registration": "registration_date",
    "Registration_Date": "registration_date",
    "Condo_Plan_No": "condo_plan_no",
    "CONDO_PLAN_NO": "condo_plan_no",
    
    # =========================================================================
    # TRANSPORTATION FIELD VARIATIONS
    # =========================================================================
    "Intersection": "intersection",
    "INTERSECTION": "intersection",
    "Street_1": "street_1",
    "STREET_1": "street_1",
    "Street_2": "street_2",
    "STREET_2": "street_2",
    "Traffic_Volume": "traffic_volume",
    "TRAFFIC_VOLUME": "traffic_volume",
    "Speed_Limit": "speed_limit",
    "SPEED_LIMIT": "speed_limit",
    "Direction": "direction",
    "DIRECTION": "direction",
    
    # =========================================================================
    # PUBLIC SAFETY FIELD VARIATIONS
    # =========================================================================
    "Incident_Type": "incident_type",
    "INCIDENT_TYPE": "incident_type",
    "Offence": "offence",
    "OFFENCE": "offence",
    "Division": "division",
    "DIVISION": "division",
    "Occurrence_Date": "occurrence_date",
    "OCCURRENCE_DATE": "occurrence_date",
    "Reported_Date": "reported_date",
    "REPORTED_DATE": "reported_date",
    "Premises_Type": "premises_type",
    "PREMISES_TYPE": "premises_type",
    "Crime_Type": "crime_type",
    "MCI_Category": "mci_category",
    
    # =========================================================================
    # ENVIRONMENT FIELD VARIATIONS
    # =========================================================================
    "Park_Name": "park_name",
    "PARK_NAME": "park_name",
    "Facility_Type": "facility_type",
    "FACILITY_TYPE": "facility_type",
    "Asset_Type": "asset_type",
    "ASSET_TYPE": "asset_type",
    
    # =========================================================================
    # BUSINESS FIELD VARIATIONS
    # =========================================================================
    "Business_Name": "business_name",
    "BUSINESS_NAME": "business_name",
    "Business_Type": "business_type",
    "BUSINESS_TYPE": "business_type",
    "License_Type": "license_type",
    "LICENSE_TYPE": "license_type",
    "License_Status": "license_status",
    "LICENSE_STATUS": "license_status",
    
    # =========================================================================
    # PERMIT FIELD VARIATIONS
    # =========================================================================
    "Permit_Type": "permit_type",
    "PERMIT_TYPE": "permit_type",
    "Permit_Status": "permit_status",
    "PERMIT_STATUS": "permit_status",
    "Permit_Number": "permit_number",
    "PERMIT_NUMBER": "permit_number",
    "Issue_Date": "issue_date",
    "ISSUE_DATE": "issue_date",
    "Expiry_Date": "expiry_date",
    "EXPIRY_DATE": "expiry_date",
}


# =============================================================================
# NORMALIZATION FUNCTIONS
# =============================================================================

def normalize_field_name(field_name: str) -> str:
    """
    Normalize a field name to standard format.
    
    1. Check direct mapping
    2. Convert to snake_case
    3. Handle special characters
    """
    # Check direct mapping first
    if field_name in FIELD_MAP:
        return FIELD_MAP[field_name]
    
    # Convert to snake_case and clean up
    normalized = field_name
    normalized = normalized.replace(" ", "_")
    normalized = normalized.replace("-", "_")
    normalized = normalized.replace(".", "")
    normalized = normalized.replace("+", "_plus_")
    normalized = normalized.replace("/", "_")
    normalized = normalized.replace("(", "")
    normalized = normalized.replace(")", "")
    
    return normalized


def sanitize_value(value: Any) -> Any:
    """
    Sanitize a value for Elasticsearch indexing.
    
    - Convert numpy types to Python types
    - Handle NaN/None values
    - Convert datetime objects
    """
    if value is None:
        return None
    
    # Handle numpy types
    if hasattr(value, "item"):
        value = value.item()
    
    # Handle NaN (float check)
    if isinstance(value, float) and value != value:
        return None
    
    # Handle datetime
    if hasattr(value, "isoformat"):
        return value.isoformat()
    
    return value


def build_searchable_text(doc: Dict, primary_issue: str) -> str:
    """
    Build combined searchable text field based on data type.
    
    This enables full-text search across the most relevant fields
    for each data type.
    """
    text_parts = []
    
    # Always include address fields
    address_fields = [
        "address", "addrFull", "street_name", 
        "neighbourhood", "ward"
    ]
    for field in address_fields:
        if doc.get(field):
            text_parts.append(str(doc[field]))
    
    # Add issue-specific fields
    issue_fields = ISSUE_SEARCH_FIELDS.get(primary_issue, [])
    for field in issue_fields:
        if doc.get(field):
            text_parts.append(str(doc[field]))
    
    # If no issue-specific fields matched, include any string fields
    if not text_parts:
        for key, value in doc.items():
            if isinstance(value, str) and len(value) < 500 and not key.startswith("_"):
                text_parts.append(value)
    
    return " | ".join(text_parts) if text_parts else ""


def generate_unique_id(dataset_id: str, record: Dict) -> str:
    """Generate a unique ID for a document based on dataset and record content."""
    id_string = f"{dataset_id}_{json.dumps(record, sort_keys=True, default=str)}"
    return hashlib.md5(id_string.encode()).hexdigest()[:16]


# =============================================================================
# DOCUMENT PREPARATION
# =============================================================================

def prepare_document(record: Dict, metadata: Dict) -> Dict:
    """
    Prepare a single record for Elasticsearch indexing.
    
    - Normalizes field names
    - Adds metadata fields
    - Builds searchable_text
    - Handles geometry/geo_point
    - Generates unique ID
    
    Args:
        record: Raw record from dataset
        metadata: Dataset metadata (_metadata from enriched JSON)
        
    Returns:
        Document ready for Elasticsearch indexing
    """
    primary_issue = metadata.get("primary_issue", "uncategorized")
    dataset_id = metadata.get("dataset_id", "unknown")
    
    # Start with metadata fields
    doc = {
        "dataset_id": dataset_id,
        "dataset_name": metadata.get("dataset_name", ""),
        "resource_name": metadata.get("resource_name", ""),
        "primary_issue": primary_issue,
        "secondary_issues": metadata.get("secondary_issues", []),
        "subcategory": metadata.get("subcategory", "general"),
        "data_type": metadata.get("data_type", "general"),
        "issue_keywords": metadata.get("issue_keywords", []),
        "matched_keywords": metadata.get("matched_keywords", []),
        "source": metadata.get("source", "toronto-open-data"),
        "loaded_at": datetime.utcnow().isoformat(),
        "@timestamp": datetime.utcnow().isoformat()
    }
    
    # Process record fields
    centroid_lat = None
    centroid_lon = None
    
    for key, value in record.items():
        # Sanitize value
        value = sanitize_value(value)
        
        # Skip None values
        if value is None:
            continue
        
        # Normalize field name
        norm_key = normalize_field_name(key)
        
        # Handle special fields
        if norm_key == "geometry" and value:
            doc["geometry"] = value
        elif norm_key == "centroid_lat":
            centroid_lat = value
            doc["centroid_lat"] = value
        elif norm_key == "centroid_lon":
            centroid_lon = value
            doc["centroid_lon"] = value
        else:
            doc[norm_key] = value
    
    # Create geo_point from centroid if available
    if centroid_lat is not None and centroid_lon is not None:
        doc["location"] = {"lat": centroid_lat, "lon": centroid_lon}
        doc["centroid"] = {"lat": centroid_lat, "lon": centroid_lon}
    
    # Build searchable text
    doc["searchable_text"] = build_searchable_text(doc, primary_issue)
    
    # Generate unique ID
    doc["_unique_id"] = generate_unique_id(dataset_id, record)
    
    return doc


def prepare_documents(records: List[Dict], metadata: Dict) -> List[Dict]:
    """Prepare multiple records for indexing."""
    return [prepare_document(record, metadata) for record in records]