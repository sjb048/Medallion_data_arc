# doc_utils.py
"""
Shared Document Utilities

Common functions for document preparation, ID generation, and normalization
used by both SyncManager and GoldLayer.
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from .es_config import SEARCHABLE_TEXT_FIELDS

# =============================================================================
# UNIQUE ID GENERATION
# =============================================================================

def generate_unique_id(doc: Dict, dataset_id: str = None) -> str:
    """
    Generate deterministic unique ID for a document.
    
    Uses stable fields to ensure same document always gets same ID.
    """
    ds_id = dataset_id or doc.get("dataset_id", "unknown")
    
    # Use identifying fields if present
    id_fields = {"dataset_id": ds_id}
    
    for field in ["id", "_id", "estName", "business_name", "address", "insDate"]:
        if field in doc and doc[field]:
            id_fields[field] = doc[field]
    
    # If no identifying fields, use content hash
    if len(id_fields) == 1:
        id_fields["content"] = json.dumps(doc, sort_keys=True, default=str)
    
    content = json.dumps(id_fields, sort_keys=True, default=str)
    return hashlib.md5(f"{ds_id}_{content}".encode()).hexdigest()[:16]


def get_doc_id(doc: Dict) -> str:
    """Get document ID, generating if needed."""
    return (
        doc.get("_unique_id") or 
        doc.get("unique_id") or 
        generate_unique_id(doc)
    )


# =============================================================================
# SEARCHABLE TEXT
# =============================================================================

def build_searchable_text(doc: Dict, fields: List[str] = None) -> str:
    """
    Build combined searchable text from document fields.
    
    Args:
        doc: Document to process
        fields: Fields to include (default: SEARCHABLE_TEXT_FIELDS)
    """
    fields = fields or SEARCHABLE_TEXT_FIELDS
    
    parts = []
    for field in fields:
        value = doc.get(field)
        if value:
            parts.append(str(value))
    
    return " | ".join(parts) if parts else ""


# =============================================================================
# GEO FIELD PROCESSING
# =============================================================================

def process_geo_fields(doc: Dict) -> None:
    """
    Process and normalize geo fields in place.
    
    Creates location/centroid geo_point from lat/lon fields.
    """
    lat = doc.get("centroid_lat") or doc.get("latitude")
    lon = doc.get("centroid_lon") or doc.get("longitude")
    
    if lat is not None and lon is not None:
        try:
            geo_point = {"lat": float(lat), "lon": float(lon)}
            doc["location"] = geo_point
            doc["centroid"] = geo_point
        except (ValueError, TypeError):
            pass


# =============================================================================
# DOCUMENT PREPARATION
# =============================================================================

def prepare_es_document(
    doc: Dict,
    dataset_id: str = None,
    add_timestamps: bool = True,
) -> Dict:
    """
    Prepare a document for Elasticsearch indexing.
    
    Args:
        doc: Source document (from MongoDB or raw)
        dataset_id: Dataset identifier
        add_timestamps: Add indexed_at/synced_at timestamps
        
    Returns:
        ES-ready document
    """
    # Copy document, exclude MongoDB _id
    es_doc = {k: v for k, v in doc.items() if k != "_id"}
    
    # Set dataset_id
    if dataset_id:
        es_doc["dataset_id"] = dataset_id
    
    # Add timestamps
    if add_timestamps:
        now = datetime.utcnow().isoformat()
        es_doc["indexed_at"] = now
        es_doc["synced_at"] = now
        if "@timestamp" not in es_doc:
            es_doc["@timestamp"] = now
    
    # Generate unique_id if missing
    if "_unique_id" not in es_doc and "unique_id" not in es_doc:
        es_doc["_unique_id"] = generate_unique_id(es_doc)
    
    # Build searchable_text if missing
    if "searchable_text" not in es_doc:
        es_doc["searchable_text"] = build_searchable_text(es_doc)
    
    # Process geo fields
    process_geo_fields(es_doc)
    
    return es_doc


def prepare_es_documents(
    docs: List[Dict],
    dataset_id: str = None,
) -> List[Dict]:
    """Prepare multiple documents for ES indexing."""
    return [prepare_es_document(doc, dataset_id) for doc in docs]


# =============================================================================
# VALUE SANITIZATION
# =============================================================================

def sanitize_value(value: Any) -> Any:
    """
    Sanitize a value for Elasticsearch.
    
    - Converts numpy types to Python types
    - Handles NaN/None
    - Converts datetime objects
    """
    if value is None:
        return None
    
    # Handle numpy types
    if hasattr(value, "item"):
        value = value.item()
    
    # Handle NaN
    if isinstance(value, float) and value != value:
        return None
    
    # Handle datetime
    if hasattr(value, "isoformat"):
        return value.isoformat()
    
    return value


def sanitize_document(doc: Dict) -> Dict:
    """Sanitize all values in a document."""
    return {k: sanitize_value(v) for k, v in doc.items()}


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "generate_unique_id", "get_doc_id", "build_searchable_text",
    "process_geo_fields", "prepare_es_document",
]