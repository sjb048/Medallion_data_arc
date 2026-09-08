# elasticsearch/__init__.py
# Unified Elasticsearch module for Toronto Open Data


from .sync_manager import (
    SyncManager,
    SyncResult,
    SyncStatus,
    quick_sync,
    full_resync,
    get_sync_status
)
from .es_config import (
    DEFAULT_ES_HOSTS,
    DEFAULT_ES_INDEX,
    DEFAULT_MONGO_URI,
    DEFAULT_MONGO_DATABASE,
    DEFAULT_SILVER_COLLECTION,
    UNIFIED_MAPPING,
    SEARCHABLE_TEXT_FIELDS,
    SEARCH_BOOST_FIELDS,
    ES_CONFIG,
   
)

from .es_doc import (
    generate_unique_id,
    get_doc_id,
    build_searchable_text,
    prepare_es_document,
)
from .transformer import (
    transform_shelter,
    transform_outbreak,
    transform_generic,
)
__all__ = [
    #sync
    "SyncManager",
    "SyncResult", 
    "SyncStatus",
    "quick_sync",
    "full_resync",
    "get_sync_status",
 
    
    # Config
    "ES_CONFIG", "DEFAULT_ES_HOSTS", "DEFAULT_ES_INDEX", 
    "DEFAULT_BATCH_SIZE", "DEFAULT_MONGO_URI", "DEFAULT_MONGO_DATABASE",
    "DEFAULT_SILVER_COLLECTION", "UNIFIED_MAPPING",
    "SEARCH_BOOST_FIELDS", "SEARCHABLE_TEXT_FIELDS",

    # Sync
    "SyncManager", "SyncResult", "SyncStatus",
    "quick_sync", "full_resync", "get_sync_status",

    # Doc utils
    "generate_unique_id",
    "get_doc_id",
    "build_searchable_text",
    "prepare_es_document",

    "transform_shelter",
    # "transform_housing",
    "transform_outbreak",
    "transform_generic",
]