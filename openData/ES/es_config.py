from typing import Dict, List, Any
import os
import sys
from pathlib import Path
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
# This file is script/OpenData/ES/es_config.py
ES_DIR = Path(__file__).resolve().parent       # .../script/OpenData/ES
OPENDATA_DIR = ES_DIR.parent                   # .../script/OpenData
SCRIPT_DIR = OPENDATA_DIR.parent               # .../script
PROJECT_ROOT = SCRIPT_DIR.parent               # .../HOLA-dashboard

# Load env.development from project root
env_path = PROJECT_ROOT / ".env.development"
load_dotenv(env_path, override=True)
load_dotenv(PROJECT_ROOT / ".env", override=False)

# print("=== ENV DEBUG ===")
# print(f"env.development path: {env_path}")
# print(f"File exists: {env_path.exists()}")
# print(f"ELASTICSEARCH_USERNAME: {os.getenv('ELASTICSEARCH_USERNAME')!r}")
# print(f"ELASTICSEARCH_PASSWORD: {os.getenv('ELASTICSEARCH_PASSWORD')!r}")
# print("=== END DEBUG ===")

# Add script/ to path so utils can be imported
for path in [str(SCRIPT_DIR), str(OPENDATA_DIR), str(OPENDATA_DIR / "common")]:
    if path not in sys.path:
        sys.path.insert(0, path)
# =============================================================================
# CONNECTION DEFAULTS
# =============================================================================
ES_CONFIG: Dict[str, Any] = {}

# Try 1: Import from utils (in script/)
try:
    from utils import get_elasticsearch_config
    _es_conf = get_elasticsearch_config(index="policy_issues_toronto")
    ES_CONFIG = {
        "hosts": _es_conf.get("hosts", []),
        "index": _es_conf.get("index", "policy_issues_toronto"),
        "username": _es_conf.get("username") or os.getenv("ELASTICSEARCH_USERNAME"),
        "password": _es_conf.get("password") or os.getenv("ELASTICSEARCH_PASSWORD"),
        "verify_certs": False,
        "ssl_show_warn": False,
        "timeout": 60,
    }
    print(f"✓ Loaded ES config from utils")
except ImportError as e:
    # print(f"  Could not import from utils: {e}")
    pass
    # hosts_str = os.getenv("ELASTICSEARCH_HOSTS", "https://207.6.138.170:9200")
hosts_str = os.getenv("ELASTICSEARCH_HOSTS", "https://207.6.138.170:9200")
hosts = [h.strip() for h in hosts_str.split(",")] if "," in hosts_str else [hosts_str]

ES_CONFIG.setdefault("hosts", hosts)
ES_CONFIG.setdefault("index", os.getenv("ELASTICSEARCH_INDEX", "policy_issues_toronto"))
ES_CONFIG["username"] = ES_CONFIG.get("username") or os.getenv("ELASTICSEARCH_USERNAME")
ES_CONFIG["password"] = ES_CONFIG.get("password") or os.getenv("ELASTICSEARCH_PASSWORD")
ES_CONFIG.setdefault("verify_certs", False)
ES_CONFIG.setdefault("ssl_show_warn", False)
ES_CONFIG.setdefault("timeout", 60)
# Try 2: Import from config_db
if not ES_CONFIG.get("password"):
    raise RuntimeError("Elasticsearch password is empty. Set ELASTICSEARCH_PASSWORD or configure get_elasticsearch_config().")

es = Elasticsearch(
    ES_CONFIG["hosts"],
    basic_auth=(ES_CONFIG["username"], ES_CONFIG["password"]),
    verify_certs=ES_CONFIG["verify_certs"],
    ssl_show_warn=ES_CONFIG["ssl_show_warn"],
    request_timeout=ES_CONFIG["timeout"],
)
DEFAULT_ES_HOSTS = ES_CONFIG['hosts']
DEFAULT_ES_INDEX = ES_CONFIG['index']
DEFAULT_BATCH_SIZE = 500

DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_MONGO_DATABASE = "policy_issues"
DEFAULT_SILVER_COLLECTION = "policy_datas"
DEFAULT_BATCH_SIZE = 500


# =============================================================================
# SEARCHABLE TEXT CONFIGURATION
# =============================================================================

SEARCHABLE_TEXT_FIELDS = [
    # Address
    "address", "addrFull", "street_name", "neighbourhood", "ward",
    # Health
    "estName", "observation", "defDesc", "comments", "beachName",
    # Business
    "business_name",
    # Environment
    "park_name", "facility_name",
    # Transportation
    "intersection", "route_name",
    # General
    "description", "name",
]

SEARCH_BOOST_FIELDS: List[str] = [
    "searchable_text^3",
    "estName^2",
    "business_name^2",
    "address^2",
    "park_name^2",
    "intersection^2"
]

# =============================================================================
# INDEX SETTINGS
# =============================================================================

INDEX_SETTINGS = {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "index.mapping.total_fields.limit": 5000,
}
# =============================================================================
# ANALYSIS (ANALYZERS / FILTERS / NORMALIZERS)
# =============================================================================

ANALYZERS = {
    "policy_analyzer": {
        "type": "custom",
        "tokenizer": "standard",
        "filter": ["lowercase", "stop", "snowball"]
    },
    "autocomplete_index": {
        "type": "custom",
        "tokenizer": "standard",
        "filter": ["lowercase", "autocomplete_filter"],
    },
}

FILTERS = {
    "autocomplete_filter": {
        "type": "edge_ngram",
        "min_gram": 2,
        "max_gram": 20
    }
}

# For case-insensitive keyword filtering/sorting (exact match but lowercased)
NORMALIZERS = {
    "lowercase_normalizer": {
        "type": "custom",
        "filter": ["lowercase"],
    }
}


# =============================================================================
# FIELD MAPPINGS
# =============================================================================

CORE_FIELDS = {
    # Identifiers
    "_unique_id": {"type": "keyword"},
    "unique_id": {"type": "keyword"},
    "doc_id": {"type": "keyword"},
    "dataset_id": {"type": "keyword"},

    "dataset_name": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {
            "keyword": {"type": "keyword", "ignore_above": 256},
            "ci": {"type": "keyword", "normalizer": "lowercase_normalizer", "ignore_above": 256},
        },
    },
    "resource_name": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {
            "keyword": {"type": "keyword", "ignore_above": 256},
            "ci": {"type": "keyword", "normalizer": "lowercase_normalizer", "ignore_above": 256},
        },
    },
    
    # Classification
    "primary_issue": {"type": "keyword"},
    "secondary_issues": {"type": "keyword"},
    "subcategory": {
        "type": "text",  
        "analyzer": "policy_analyzer",
        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
        },
    "data_type": {"type": "keyword"},
    "issue_keywords": {"type": "keyword"},
    "matched_keywords": {"type": "keyword"},
    
    # Timestamps
    "@timestamp": {"type": "date"},
    "loaded_at": {"type": "date"},
    "indexed_at": {"type": "date"},
    "synced_at": {"type": "date"},
    
    # Searchable text
    "searchable_text": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {
            "autocomplete": {
                "type": "text",
                "analyzer": "autocomplete_index",      # index-time ngrams
                "search_analyzer": "policy_analyzer",  # query-time normal analysis
            }
        },
    },
    
    # Common
    "status": {"type": "keyword"},
    "type": {"type": "keyword"},
    "category": {"type": "keyword"},
    "year": {"type": "integer"},
    "month": {"type": "integer"},
}

GEO_FIELDS = {
    "geometry": {"type": "geo_shape", "ignore_malformed": True},
    "location": {"type": "geo_point", "ignore_malformed": True},
    "centroid": {"type": "geo_point", "ignore_malformed": True},
    "centroid_lat": {"type": "float"},
    "centroid_lon": {"type": "float"},
    "latitude": {"type": "float"},
    "longitude": {"type": "float"},
}

ADDRESS_FIELDS = {
    "address": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {
            "keyword": {"type": "keyword", "ignore_above": 256},
            "ci": {"type": "keyword", "normalizer": "lowercase_normalizer", "ignore_above": 256},
        },
    },
    "addrFull": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {
            "keyword": {"type": "keyword", "ignore_above": 256},
            "ci": {"type": "keyword", "normalizer": "lowercase_normalizer", "ignore_above": 256},
        },
    },
    "street_name": {"type": "text", "analyzer": "policy_analyzer",
                    "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},},
    "ward": {"type": "keyword"},
    "neighbourhood": {"type": "text", "analyzer": "policy_analyzer", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},},
}

DOMAIN_FIELDS = {
    # Health
    "estName": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
    },
    "insStatus": {"type": "keyword"},
    "insDate": {"type": "date", "format": "yyyy-MM-dd||epoch_millis", "ignore_malformed": True},
    "infCategory": {"type": "keyword"},
    "severity": {"type": "keyword"},
    
    # Business
    "business_name": {
        "type": "text",
        "analyzer": "policy_analyzer",
        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
    },
    
    # Environment
    "park_name": {"type": "text", "analyzer": "policy_analyzer", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
    "facility_name": {"type": "text", "analyzer": "policy_analyzer", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
    
    # Transportation
    "intersection": {"type": "text", "analyzer": "policy_analyzer", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
    "route_name": {"type": "text", "analyzer": "policy_analyzer", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
}
# =============================================================================
# DYNAMIC TEMPLATES
# =============================================================================

DYNAMIC_TEMPLATES = [
    # IDs → keyword
    {"ids_as_keyword": {"match": "*_id","mapping": {"type": "keyword"}}},

    # Codes → keyword
    {"codes_as_keyword": {"match": "*_code","mapping": {"type": "keyword"}}},

    # Numbers → keyword
    {"numbers_as_keyword": {"match": "*_no","mapping": {"type": "keyword"}}},

    # Percentages → float
    {"percentages_as_float": {"match": "*_pct","mapping": {"type": "float"}}},

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
                    "keyword": {"type": "keyword", "ignore_above": 256},
                    "ci": {"type": "keyword", "normalizer": "lowercase_normalizer", "ignore_above": 256},
                },
            },
        }
    },
]



# =============================================================================
# BUILD UNIFIED MAPPING
# =============================================================================

def build_mapping() -> Dict:
    """Build complete ES mapping from components."""
    properties = {}
    properties.update(CORE_FIELDS)
    properties.update(GEO_FIELDS)
    properties.update(ADDRESS_FIELDS)
    properties.update(DOMAIN_FIELDS)
    
    return {
        "settings": {
            **INDEX_SETTINGS,
            "analysis": {
                "analyzer": ANALYZERS,
                "filter": FILTERS,
                "normalizer": NORMALIZERS,
            }
        },
        "mappings": {
            "dynamic": True,
            "dynamic_templates": DYNAMIC_TEMPLATES,
            "properties": properties
        }
    }


# Pre-built mapping
UNIFIED_MAPPING = build_mapping()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [

    "ES_CONFIG","DEFAULT_BATCH_SIZE",
    "DEFAULT_ES_HOSTS", "DEFAULT_ES_INDEX",
    "DEFAULT_MONGO_URI", "DEFAULT_MONGO_DATABASE", "DEFAULT_SILVER_COLLECTION", 
    "UNIFIED_MAPPING", "SEARCHABLE_TEXT_FIELDS", "SEARCH_BOOST_FIELDS",
]
