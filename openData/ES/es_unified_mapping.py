# es_unified_mapping.py
# Unified Elasticsearch mapping for ALL Toronto Open Data types
# Supports: health, housing, transportation, public_safety, environment, business, etc.

from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk
from datetime import datetime
import hashlib
import json
import os
import logging

logger = logging.getLogger(__name__)



# =============================================================================
# FIELD NORMALIZATIONS
# =============================================================================

FIELD_MAP = {
    # Address
    "addr_full": "addrFull", "address_full": "addrFull", "Street_Name": "street_name",
    "Street_No": "street_no", "Postal_Code": "postal_code",
    # Health
    "establishment_name": "estName", "est_name": "estName", "inspection_date": "insDate",
    "inspection_status": "insStatus", "e_coli": "eColi", "E_Coli": "eColi",
    "Beach_Name": "beachName", "Site_Name": "siteName", "Collection_Date": "collectionDate",
    # Housing
    "Total_Units": "total_units", "Bachelor_Units": "bachelor_units",
    "One_Bedroom_Units": "one_bedroom_units", "Two_Bedroom_Units": "two_bedroom_units",
    "Three_+_Bedroom_Units": "three_plus_bedroom_units",
    "Bachelor_Units_Pct": "bachelor_units_pct", "One_Bedroom_Units_Pct": "one_bedroom_units_pct",
    "Two_Bedroom_Units_Pct": "two_bedroom_units_pct",
    "Three_+_Bedroom_Units_Pct": "three_plus_bedroom_units_pct",
    "Date_of_Registration": "registration_date", "Condo_Plan_No": "condo_plan_no",
}


# =============================================================================
# SEARCHABLE TEXT BUILDER
# =============================================================================

ISSUE_SEARCH_FIELDS = {
    "health": ["estName", "observation", "defDesc", "comments", "beachName", "siteName", "infCategory"],
    "housing": ["building_name", "building_type", "property_type", "condo_plan_no"],
    "transportation": ["intersection", "street_1", "street_2", "route_name", "direction"],
    "public_safety": ["incident_type", "offence", "division", "premises_type", "crime_type"],
    "environment": ["park_name", "facility_type", "asset_type"],
    "business_and_economy": ["business_name", "business_type", "license_type"],
}

def build_searchable_text(doc: dict, primary_issue: str) -> str:
    """Build combined searchable text based on data type."""
    parts = []
    
    # Always include address
    for f in ["address", "addrFull", "street_name", "neighbourhood", "ward"]:
        if doc.get(f):
            parts.append(str(doc[f]))
    
    # Add issue-specific fields
    for f in ISSUE_SEARCH_FIELDS.get(primary_issue, []):
        if doc.get(f):
            parts.append(str(doc[f]))
    
    return " | ".join(parts)



    

# =============================================================================
# USAGE EXAMPLES
# =============================================================================

if __name__ == "__main__":
    # Connect
    indexer = UnifiedIndexer(index_name="toronto-opendata")
    
    # Create index
    indexer.create_index()
    
    # Index all data
    # indexer.index_directory("./data/json")
    
    # Search examples
    print("\n🔍 Search Examples:")
    
    # All health inspection failures
    # results = indexer.search_health(query="fail", filters={"insStatus": "Fail"})
    
    # Housing near downtown
    # results = indexer.search_housing(geo={"lat": 43.65, "lon": -79.38, "distance": "3km"})
    
    # Traffic data for specific intersection
    # results = indexer.search_transportation(query="King Queen")
    
    # Get stats
    print(indexer.get_stats())