# elasticsearch/mapping.py
# Elasticsearch mapping definitions for all Toronto Open Data types

from .config import INDEX_SETTINGS, ANALYZERS, FILTERS, DYNAMIC_TEMPLATES

# =============================================================================
# COMMON FIELDS - Used by all data types
# =============================================================================

COMMON_FIELDS = {
    # Identifiers
    "doc_id": {"type": "keyword"},
    "_unique_id": {"type": "keyword"},
    "dataset_id": {"type": "keyword"},
    "dataset_name": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "resource_name": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    
    # Issue taxonomy
    "primary_issue": {"type": "keyword"},
    "secondary_issues": {"type": "keyword"},
    "subcategory": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "data_type": {"type": "keyword"},
    "issue_keywords": {"type": "keyword"},
    "matched_keywords": {"type": "keyword"},
    
    # Full-text search
    "searchable_text": {
        "type": "text",
        "analyzer": "policy_analyzer"
    },
    
    # Timestamps
    "@timestamp": {"type": "date"},
    "loaded_at": {"type": "date"},
    "source": {"type": "keyword"},
    
    # Common time fields
    "year": {"type": "integer"},
    "month": {"type": "integer"},
    "date": {
        "type": "date",
        "format": "yyyy-MM-dd||yyyy-MM-dd HH:mm:ss||epoch_millis",
        "ignore_malformed": True
    },
    
    # Common status
    "status": {"type": "keyword"},
    "type": {"type": "keyword"},
    "category": {"type": "keyword"},
}

# =============================================================================
# GEOSPATIAL FIELDS
# =============================================================================

GEO_FIELDS = {
    "geometry": {"type": "geo_shape", "ignore_malformed": True},
    "geometry_type": {"type": "keyword"},
    "location": {"type": "geo_point", "ignore_malformed": True},
    "centroid": {"type": "geo_point", "ignore_malformed": True},
    "centroid_lat": {"type": "float"},
    "centroid_lon": {"type": "float"},
    "latitude": {"type": "float"},
    "longitude": {"type": "float"},
}

# =============================================================================
# ADDRESS FIELDS
# =============================================================================

ADDRESS_FIELDS = {
    "address": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "addrFull": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "street_name": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "street_no": {"type": "keyword"},
    "unit_no": {"type": "keyword"},
    "postal_code": {"type": "keyword"},
    "city": {"type": "keyword"},
    "province": {"type": "keyword"},
    "ward": {"type": "keyword"},
    "ward_name": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "neighbourhood": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
}

# =============================================================================
# HEALTH DATA FIELDS (DineSafe, BodySafe, Beaches, etc.)
# =============================================================================

HEALTH_FIELDS = {
    # Establishment info
    "estName": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "srvType": {"type": "keyword"},
    
    # Inspection fields
    "insStatus": {"type": "keyword"},
    "insDate": {
        "type": "date",
        "format": "yyyy-MM-dd||epoch_millis",
        "ignore_malformed": True
    },
    "observation": {
        "type": "text",
        "analyzer": "policy_analyzer"
    },
    
    # Infraction fields
    "infCategory": {"type": "keyword"},
    "infType": {"type": "keyword"},
    "defDesc": {
        "type": "text",
        "analyzer": "policy_analyzer"
    },
    "severity": {"type": "keyword"},
    "action": {"type": "keyword"},
    
    # Beach water quality
    "beachName": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "siteName": {"type": "keyword"},
    "collectionDate": {
        "type": "date",
        "format": "yyyy-MM-dd||epoch_millis",
        "ignore_malformed": True
    },
    "eColi": {"type": "float"},
    "turbidity": {"type": "float"},
    "waterTemp": {"type": "float"},
    "comments": {
        "type": "text",
        "analyzer": "policy_analyzer"
    },
    "beachAdvisory": {"type": "keyword"},
}

# =============================================================================
# HOUSING DATA FIELDS
# =============================================================================

HOUSING_FIELDS = {
    # Building info
    "building_name": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "building_type": {"type": "keyword"},
    "property_type": {"type": "keyword"},
    "condo_plan_no": {"type": "keyword"},
    "registration_date": {
        "type": "date",
        "format": "yyyy-MM-dd||epoch_millis",
        "ignore_malformed": True
    },
    
    # Unit counts
    "total_units": {"type": "integer"},
    "bachelor_units": {"type": "integer"},
    "one_bedroom_units": {"type": "integer"},
    "two_bedroom_units": {"type": "integer"},
    "three_plus_bedroom_units": {"type": "integer"},
    "commercial_units": {"type": "integer"},
    "residential_units": {"type": "integer"},
    
    # Percentages
    "bachelor_units_pct": {"type": "float"},
    "one_bedroom_units_pct": {"type": "float"},
    "two_bedroom_units_pct": {"type": "float"},
    "three_plus_bedroom_units_pct": {"type": "float"},
    
    # Rental/Affordable
    "affordable_units": {"type": "integer"},
    "rent_amount": {"type": "float"},
    "average_rent": {"type": "float"},
    
    # Building details
    "storeys": {"type": "integer"},
    "year_built": {"type": "integer"},
    "year_registered": {"type": "integer"},
    "evaluation_score": {"type": "float"},
}

# =============================================================================
# TRANSPORTATION DATA FIELDS
# =============================================================================

TRANSPORTATION_FIELDS = {
    # Intersection/Location
    "intersection": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "street_1": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "street_2": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "midblock_route": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    
    # Volume counts
    "traffic_volume": {"type": "integer"},
    "pedestrian_volume": {"type": "integer"},
    "cyclist_volume": {"type": "integer"},
    "vehicle_volume": {"type": "integer"},
    "daily_volume": {"type": "integer"},
    "peak_hour_volume": {"type": "integer"},
    
    # Speed/Safety
    "speed_limit": {"type": "integer"},
    "posted_speed": {"type": "integer"},
    "average_speed": {"type": "float"},
    
    # Direction/Signal
    "direction": {"type": "keyword"},
    "signal_type": {"type": "keyword"},
    "signal_timing": {"type": "integer"},
    
    # Transit
    "route_name": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "route_number": {"type": "keyword"},
    "ttc_line": {"type": "keyword"},
    "ttc_station": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "stop_id": {"type": "keyword"},
}

# =============================================================================
# PUBLIC SAFETY DATA FIELDS
# =============================================================================

PUBLIC_SAFETY_FIELDS = {
    # Incident info
    "incident_type": {"type": "keyword"},
    "incident_id": {"type": "keyword"},
    "event_id": {"type": "keyword"},
    
    # Crime details
    "offence": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "crime_type": {"type": "keyword"},
    "mci_category": {"type": "keyword"},
    
    # Location/Division
    "division": {"type": "keyword"},
    "premises_type": {"type": "keyword"},
    "hood_id": {"type": "keyword"},
    
    # Dates
    "occurrence_date": {
        "type": "date",
        "format": "yyyy-MM-dd||epoch_millis",
        "ignore_malformed": True
    },
    "reported_date": {
        "type": "date",
        "format": "yyyy-MM-dd||epoch_millis",
        "ignore_malformed": True
    },
    "occurrence_year": {"type": "integer"},
    "occurrence_month": {"type": "integer"},
    "occurrence_day": {"type": "integer"},
    "occurrence_hour": {"type": "integer"},
}

# =============================================================================
# ENVIRONMENT DATA FIELDS
# =============================================================================

ENVIRONMENT_FIELDS = {
    # Parks/Facilities
    "park_name": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "park_id": {"type": "keyword"},
    "facility_type": {"type": "keyword"},
    "facility_name": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "asset_type": {"type": "keyword"},
    "asset_id": {"type": "keyword"},
    
    # Trees
    "tree_species": {"type": "keyword"},
    "tree_id": {"type": "keyword"},
    "dbh": {"type": "float"},  # Diameter at breast height
    
    # Measurements
    "measurement_value": {"type": "float"},
    "measurement_unit": {"type": "keyword"},
    "air_quality_index": {"type": "float"},
    
    # Ravines
    "ravine_name": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
}

# =============================================================================
# BUSINESS/ECONOMY DATA FIELDS
# =============================================================================

BUSINESS_FIELDS = {
    "business_name": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "business_type": {"type": "keyword"},
    "business_id": {"type": "keyword"},
    "license_type": {"type": "keyword"},
    "license_status": {"type": "keyword"},
    "license_no": {"type": "keyword"},
    "employees": {"type": "integer"},
    "industry_code": {"type": "keyword"},
    "naics_code": {"type": "keyword"},
}

# =============================================================================
# PERMITS DATA FIELDS
# =============================================================================

PERMIT_FIELDS = {
    "permit_type": {"type": "keyword"},
    "permit_status": {"type": "keyword"},
    "permit_number": {"type": "keyword"},
    "application_number": {"type": "keyword"},
    "issue_date": {
        "type": "date",
        "format": "yyyy-MM-dd||epoch_millis",
        "ignore_malformed": True
    },
    "expiry_date": {
        "type": "date",
        "format": "yyyy-MM-dd||epoch_millis",
        "ignore_malformed": True
    },
    "application_date": {
        "type": "date",
        "format": "yyyy-MM-dd||epoch_millis",
        "ignore_malformed": True
    },
    "completed_date": {
        "type": "date",
        "format": "yyyy-MM-dd||epoch_millis",
        "ignore_malformed": True
    },
    "permit_value": {"type": "float"},
}

# =============================================================================
# SOCIAL SERVICES DATA FIELDS
# =============================================================================

SOCIAL_SERVICES_FIELDS = {
    "program_name": {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}}
    },
    "service_type": {"type": "keyword"},
    "eligibility": {"type": "text"},
    "capacity": {"type": "integer"},
    "occupancy": {"type": "integer"},
    "availability": {"type": "keyword"},
}


# =============================================================================
# BUILD UNIFIED MAPPING
# =============================================================================

def build_unified_mapping() -> dict:
    """Build the complete unified mapping for all data types."""
    
    # Combine all field definitions
    all_properties = {}
    all_properties.update(COMMON_FIELDS)
    all_properties.update(GEO_FIELDS)
    all_properties.update(ADDRESS_FIELDS)
    all_properties.update(HEALTH_FIELDS)
    all_properties.update(HOUSING_FIELDS)
    all_properties.update(TRANSPORTATION_FIELDS)
    all_properties.update(PUBLIC_SAFETY_FIELDS)
    all_properties.update(ENVIRONMENT_FIELDS)
    all_properties.update(BUSINESS_FIELDS)
    all_properties.update(PERMIT_FIELDS)
    all_properties.update(SOCIAL_SERVICES_FIELDS)
    
    return {
        "settings": {
            **INDEX_SETTINGS,
            "analysis": {
                "analyzer": ANALYZERS,
                "filter": FILTERS
            }
        },
        "mappings": {
            "dynamic_templates": DYNAMIC_TEMPLATES,
            "properties": all_properties
        }
    }


# Pre-built mapping for direct use
UNIFIED_MAPPING = build_unified_mapping()


# =============================================================================
# FIELD GROUPS BY ISSUE TYPE (for searchable_text building)
# =============================================================================

ISSUE_SEARCH_FIELDS = {
    "health": [
        "estName", "observation", "defDesc", "comments", 
        "beachName", "siteName", "infCategory", "srvType"
    ],
    "housing": [
        "building_name", "building_type", "property_type", 
        "condo_plan_no"
    ],
    "transportation": [
        "intersection", "street_1", "street_2", "route_name",
        "ttc_station", "direction"
    ],
    "public_safety": [
        "incident_type", "offence", "division", 
        "premises_type", "crime_type", "mci_category"
    ],
    "environment": [
        "park_name", "facility_name", "facility_type",
        "asset_type", "tree_species", "ravine_name"
    ],
    "business_and_economy": [
        "business_name", "business_type", "license_type"
    ],
    "permits": [
        "permit_type", "permit_status"
    ],
    "poverty_reduction": [
        "program_name", "service_type"
    ]
}