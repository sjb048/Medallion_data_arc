# elasticsearch/config.py
# Elasticsearch configuration - settings, analyzers, and connection config


# Adding New Data Types
# To add a new data type (e.g., "education"):

# mapping.py - Add EDUCATION_FIELDS dict
# mapping.py - Add to build_unified_mapping()
# mapping.py - Add to ISSUE_SEARCH_FIELDS
# normalizer.py - Add field normalizations to FIELD_MAP
# searcher.py - Add search_education() method

# =============================================================================
# INDEX SETTINGS
# =============================================================================

INDEX_SETTINGS = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "1s",
    "max_result_window": 50000,
}

# =============================================================================
# ANALYZERS
# =============================================================================

ANALYZERS = {
    "policy_analyzer": {
        "type": "custom",
        "tokenizer": "standard",
        "filter": ["lowercase", "stop", "snowball"]
    },
    "lowercase_keyword": {
        "type": "custom",
        "tokenizer": "keyword",
        "filter": ["lowercase"]
    },
    "autocomplete": {
        "type": "custom",
        "tokenizer": "standard",
        "filter": ["lowercase", "edge_ngram_filter"]
    }
}

FILTERS = {
    "edge_ngram_filter": {
        "type": "edge_ngram",
        "min_gram": 2,
        "max_gram": 15
    }
}

# =============================================================================
# DYNAMIC TEMPLATES
# =============================================================================

DYNAMIC_TEMPLATES = [
    # IDs → keyword
    {
        "ids_as_keyword": {
            "match": "*_id",
            "mapping": {"type": "keyword"}
        }
    },
    # Codes → keyword
    {
        "codes_as_keyword": {
            "match": "*_code",
            "mapping": {"type": "keyword"}
        }
    },
    # Numbers → keyword
    {
        "numbers_as_keyword": {
            "match": "*_no",
            "mapping": {"type": "keyword"}
        }
    },
    # Percentages → float
    {
        "percentages_as_float": {
            "match": "*_pct",
            "mapping": {"type": "float"}
        }
    },
    # Dates
    {
        "dates": {
            "match": "*_date",
            "mapping": {
                "type": "date",
                "format": "yyyy-MM-dd||yyyy-MM-dd HH:mm:ss||epoch_millis",
                "ignore_malformed": True
            }
        }
    },
    # Coordinates
    {
        "coordinates": {
            "match_pattern": "regex",
            "match": "(lat|lon|latitude|longitude|x_coord|y_coord)",
            "mapping": {"type": "float"}
        }
    },
    # Default strings → text + keyword
    {
        "strings_as_text_keyword": {
            "match_mapping_type": "string",
            "mapping": {
                "type": "text",
                "analyzer": "policy_analyzer",
                "fields": {
                    "keyword": {"type": "keyword", "ignore_above": 256}
                }
            }
        }
    }
]

# =============================================================================
# DEFAULT CONNECTION CONFIG
# =============================================================================

DEFAULT_ES_CONFIG = {
    "host": "http://localhost:9200",
    "index_name": "toronto-opendata",
    "timeout": 60,
    "retry_on_timeout": True,
    "max_retries": 3
}

# =============================================================================
# ISSUE TYPES (for reference)
# =============================================================================

ISSUE_TYPES = [
    "health",
    "housing", 
    "transportation",
    "public_safety",
    "environment",
    "business_and_economy",
    "poverty_reduction",
    "permits",
    "demographics",
    "uncategorized"
]

# =============================================================================
# DATA TYPES (for reference)
# =============================================================================

DATA_TYPES = [
    "inspection",
    "measurement", 
    "inventory",
    "statistics",
    "geospatial",
    "general"
]