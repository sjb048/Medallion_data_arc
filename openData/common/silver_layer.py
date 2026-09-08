# silver_layer.py
"""
SILVER LAYER - Normalized Data Storage

Transforms and normalizes raw data for consistent querying.
Can reprocess from Bronze layer when rules change.

MongoDB Collection: policy_records

Usage:
    from silver_layer import SilverLayer
    
    silver = SilverLayer()
    silver.store(record, dataset_id="outbreaks", metadata={...})
    silver.reprocess_from_bronze(bronze_layer, dataset_id="outbreaks")
"""

import re
import json
import hashlib
import sys
from datetime import datetime
import resource
from typing import Dict, List, Any, Optional, Callable
from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection

from pathlib import Path
from starlette.middleware.trustedhost import TrustedHostMiddleware


# Add paths for imports
script_dir = Path(__file__).resolve().parent.parent 
project_root = script_dir.parent.parent #HOLA-dashboard
print(f"Project root for bronze_layer: {project_root}")

sys.path.insert(0, str(project_root))
from utils import get_mongodb_uri




# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS FROM COMMON MODULES
# ────────────────────────────────────────────────────────────────────────────

from common.metadata import build_metadata
from common.searchable_text_builder import build_searchable_text, SEARCHABLE_FIELDS

try:
    from common.mapping import FIELD_MAP, BOOLEAN_FIELDS, NULL_VALUES
except ImportError:
    FIELD_MAP = {}
    BOOLEAN_FIELDS = {"is_active", "active"}
    NULL_VALUES = {"n/a", "na", "none", "null", "unknown", "-", "", "unable to identify"}
    print(f"import error from silver_layer for mapping field")


# Import taxonomy
try:
    from common.taxonomy import ISSUE_TAXONOMY, DATASET_ISSUE_MAP
except ImportError:
    # Fallback if taxonomy not available
    ISSUE_TAXONOMY = {}
    DATASET_ISSUE_MAP = {}
    print(f"import error from silver_layer for taxonomy")



class SilverLayer:
    """
    Silver Layer: Normalized data storage.
    
    TRANSFORMS:
    - Field names → snake_case
    - Values → cleaned (nulls, booleans, dates)
    - Adds searchable_text for full-text search
    - Adds metadata and tags
    
    Schema:
        {
            "_unique_id": "dataset_recordid",
            "dataset_id": "outbreaks",
            "original_id": 123,
            "loaded_at": datetime,
            "primary_issue": "health",
            "secondary_issues": ["housing"],
            "searchable_text": "...",
            ... normalized fields ...
        }
    """
    
    COLLECTION_NAME = "policy_datas"
    
    def __init__(
        self,
        mongo_uri:str = None,
        database: str = "policy_issues",
        domain_config = None,
        collection: str = None,
        field_map: Dict[str, str] = None,
        taxonomy: Dict = None,
        dataset_issue_map: Dict = None
    ):
        """
        Initialize Silver Layer.
        
        Args:
            mongo_uri: MongoDB connection string
            database: Database name
            collection: Collection name (default: policy_records)
            field_map: Custom field name mappings
        """
        self.client = MongoClient(mongo_uri)
        self.db = self.client[database]
        self.collection: Collection = self.db[collection or self.COLLECTION_NAME]
        # Domain configuration
        self.domain_config = domain_config

        # Build field map from domain config + overrides
        self.field_map = {**FIELD_MAP, **(field_map or {})}
        
        # Taxonomy for issue classification
        self.taxonomy = taxonomy or ISSUE_TAXONOMY
        self.dataset_issue_map = dataset_issue_map or DATASET_ISSUE_MAP

        # Create indexes
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create indexes for efficient queries."""
        self.collection.create_index("_unique_id", unique=True)
        self.collection.create_index("dataset_id")
        self.collection.create_index("domain")
        self.collection.create_index("primary_issue")
        self.collection.create_index("loaded_at")
        self.collection.create_index([("searchable_text", "text")])
    
    # =========================================================================
    # TAXONOMY-BASED ISSUE TAGGING
    # =========================================================================
    

    def get_issue_tags(self, dataset_id: str) -> dict:
        """Get issue tags for a dataset based on taxonomy"""
        
        # Check explicit mapping first
        if dataset_id in self.dataset_issue_map:
            mapping = self.dataset_issue_map[dataset_id]
            primary = mapping.get("primary", "uncategorized")
            return {
                "primary_issue": primary,
                "secondary_issues": mapping.get("secondary", []),
                "subcategory": mapping.get("subcategory", "general"),
                "issue_keywords": self.taxonomy.get(primary, {}).get("keywords", [])
            }
        
        # Fallback: try to match by keywords in dataset name
        dataset_lower = dataset_id.lower()
        for issue, data in self.taxonomy.items():
            for keyword in data.get("keywords", []):
                if keyword in dataset_lower:
                    return {
                        "primary_issue": issue,
                        "secondary_issues": [],
                        "subcategory": "general",
                        "issue_keywords": data.get("keywords", [])
                    }   
       
        # Default: uncategorized
        return {
            "primary_issue": "uncategorized",
            "secondary_issues": [],
            "subcategory": "general",
            "issue_keywords": []
        }
    
    def detect_data_type(self, records: list[Dict]) -> str:
        """Detect the type of data (inspection, measurement, inventory, etc.)"""
        if not records:
            return "unknown"
        
        sample = records[0]
        keys_lower = [k.lower() for k in sample.keys()]
        all_keys = " ".join(keys_lower)
        
        # Check for inspection data
        inspection_keywords = ["inspection", "infraction", "severity", "pass", "fail", "status", "establishment"]
        if any(kw in all_keys for kw in inspection_keywords):
            return "inspection"
        
        # Check for incident/outbreak data
        incident_keywords = ["outbreak", "incident", "case", "date_declared", "causative", "active"]
        if any(kw in all_keys for kw in incident_keywords):
            return "incident"
        
        # Check for observation data (e.g., beach observations)
        observation_keywords = ["observation", "sample", "reading", "measurement", "count", "level"]
        if any(kw in all_keys for kw in observation_keywords):
            return "observation"
        
        # Check for registry data (e.g., building registrations)
        registry_keywords = ["registration", "registered", "license", "permit", "certificate"]
        if any(kw in all_keys for kw in registry_keywords):
            return "registry"
        
        # Check for statistics/summary data
        stats_keywords = ["total", "count", "average", "rate", "percentage", "summary", "annual"]
        if any(kw in all_keys for kw in stats_keywords):
            return "statistics"
        
        # Check for location data
        location_keywords = ["latitude", "longitude", "geometry", "coordinates", "location", "address"]
        if any(kw in all_keys for kw in location_keywords):
            return "location"
        
        return "general"
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def store(
        self,
        record: Dict,
        dataset_id: str,
        resource: Dict = None,
        package_info: Dict = None,
        extra_metadata: Dict = None
    ) -> str:
        """
        Normalize and store a single record.
        
        Args:
            record: Raw record to normalize
            dataset_id: Dataset identifier
            metadata: Additional metadata (primary_issue, etc.)
            
        Returns:
            The _unique_id of the stored record
        """
        
        metadata = build_metadata(
            package_name=dataset_id, 
            resource=resource,
            package_info=package_info,
            record_count=1,
            extra=extra_metadata
        )
        
        resource_scope = ""
        if resource:
            resource_scope = resource.get("id") or resource.get("name") or ""
        # Generate unique ID
        unique_id = self._generate_id(record, dataset_id, resource_scope=resource_scope)
        
        # Build normalized document
        doc = self._build_document(record, dataset_id, unique_id, metadata)
        # print(f"here is the {doc}")
        # Store
        self.collection.update_one(
            {"_unique_id": unique_id},
            {"$set": doc},
            upsert=True
        )
        
        return unique_id
    
    def store_batch(
        self,
        records: List[Dict],
        dataset_id: str,
        resource: Dict = None,
        package_info: Dict = None,
        extra_metadata: Dict = None
    ) -> Dict[str, int]:
        """
        Normalize and store multiple records efficiently.
        
        Args:
            records: List of raw records
            dataset_id: Dataset identifier
            metadata: Additional metadata
            
        Returns:
            Stats dict with counts
        """
        print(f" Storing batch of {len(records)} records for dataset {dataset_id}...")
        if not records:
            return {"stored": 0, "errors": 0}
        

        metadata = build_metadata(
            package_name=dataset_id, 
            resource=resource,
            package_info=package_info,
            record_count=len(records),
            extra=extra_metadata
        )
        operations = []

        resource_scope = ""
        if resource:
            resource_scope = resource.get("id") or resource.get("name") or ""
        
        for record in records:
            unique_id = self._generate_id(record, dataset_id, resource_scope=resource_scope)
            doc = self._build_document(record, dataset_id, unique_id, metadata)
            # print(f"here is the bulk {doc}")
            operations.append(
                UpdateOne(
                    {"_unique_id": unique_id},
                    {"$set": doc},
                    upsert=True
                )
            )
        
        # Bulk write
        result = self.collection.bulk_write(operations, ordered=False)
        
        return {
            "stored": result.upserted_count + result.modified_count,
            "matched": result.matched_count,
            "upserted": result.upserted_count
        }
    
    def normalize_record(self, record: Dict) -> Dict:
        """
        Normalize a single record without storing.
        
        Useful for transformations in other pipelines.
        
        Args:
            record: Raw record
            
        Returns:
            Normalized record
        """
        normalized = {}
        
        for key, value in record.items():
            if key == "_id":
                normalized["original_id"] = value
                continue
            
            if key.startswith("_"):
                continue
            
            norm_key = self.field_map.get(key, self._to_snake_case(key))
            norm_value = self._normalize_value(norm_key, value)
            normalized[norm_key] = norm_value
        
        return normalized
    
    
    
    def tag_and_enrich_data(
        self,
        records: List[Dict],
        package_name: str,
        resource_name: str,
        package_metadata: Dict,
        source_format: str,
        resource_id: str = None
    ) -> Dict:
        """
        Tag and enrich data with metadata (for JSON file output).
        
        Returns structure compatible with your existing format.
        """
        issue_tags = self.get_issue_tags(package_name)
        data_type = self.detect_data_type(records)
        
        enriched_data = {
            "_metadata": {
                "source": "toronto-open-data",
                "dataset_id": package_name,
                "dataset_name": package_metadata.get("title", package_name),
                "resource_name": resource_name,
                "resource_id": resource_id,
                "source_format": source_format,
                "download_date": datetime.utcnow().isoformat(),
                "record_count": len(records),
                
                # Issue tagging from taxonomy
                "primary_issue": issue_tags["primary_issue"],
                "secondary_issues": issue_tags["secondary_issues"],
                "subcategory": issue_tags["subcategory"],
                "issue_keywords": issue_tags["issue_keywords"],
                
                # For alignment engine
                "alignment_ready": True,
                "data_type": data_type,
            },
            "records": [self.normalize_record(r) for r in records]
        }
        
        return enriched_data
    
    # =========================================================================
    # document building
    # =========================================================================
    
    def _build_document(
        self,
        record: Dict,
        dataset_id: str,
        unique_id: str,
        metadata: Dict
    ) -> Dict:
        """Build normalized document from raw record."""
        
        # Start with metadata
        doc = {
            "_unique_id": unique_id,
            "dataset_id": dataset_id,
            "loaded_at": datetime.utcnow()
            
        }
        
        if self.domain_config:
            doc["domain"] = self.domain_config.domain_name
            doc["primary_issue"] = getattr(self.domain_config, 'primary_issue', None)
            doc["secondary_issues"] = getattr(self.domain_config, 'secondary_issues', [])

        #add metadata
        doc["primary_issue"] = metadata.get("primary_issue", doc.get("primary_issue"))
        doc["secondary_issues"] = metadata.get("secondary_issues", doc.get("secondary_issues", []))
        doc["subcategory"] = metadata.get("subcategory")
        doc["data_type"] = metadata.get("data_type")
        doc["issue_keywords"] = metadata.get("issue_keywords", [])

        normalized = self.normalize_record(record)
        doc.update(normalized)

        # ─────────────────────────────────────────────────────────────────────
        # 4. ENRICHMENT: TAGS
        # ─────────────────────────────────────────────────────────────────────
        # doc["tags"] = self._generate_tags(record, metadata)
        
        doc["searchable_text"] = build_searchable_text(doc)
        
        return doc
    
    def _generate_tags(self, record: Dict, metadata: Dict) -> List[str]:
        """
        Generate tags based on record content and metadata.
        """
        tags = set()
        
        # Add domain tag
        if metadata.get("domain"):
            tags.add(metadata["domain"])
        
        # Add primary issue tag
        if metadata.get("primary_issue"):
            tags.add(metadata["primary_issue"])
        
        # Add civic issues as tags
        for issue in metadata.get("civic_issues") or []:
            if issue:
                tags.add(issue.lower().replace(" ", "_"))
        
        # Add topics as tags
        for topic in metadata.get("topics") or []:
            if topic:
                tags.add(topic.lower().replace(" ", "_"))
        
        # ─────────────────────────────────────────────────────────────────────
        # CONTENT-BASED TAGS
        # ─────────────────────────────────────────────────────────────────────
        
        # Outbreak type
        outbreak_type = record.get("outbreak_type") or record.get("type_of_outbreak") or record.get("Type of Outbreak")
        if outbreak_type:
            tags.add(f"outbreak_{outbreak_type.lower().replace(' ', '_')}")
            tags.add("outbreak")
        
        # Active status
        is_active = record.get("is_active") or record.get("active") or record.get("Active")
        if is_active in (True, "Y", "Yes", "YES"):
            tags.add("active")
        elif is_active in (False, "N", "No", "NO"):
            tags.add("resolved")
        
        # Establishment type
        est_type = record.get("establishment_type") or record.get("type") or record.get("Establishment Type")
        if est_type:
            tags.add(est_type.lower().replace(" ", "_"))
        
        # Severity
        severity = record.get("severity") or record.get("infraction_severity") or record.get("Severity")
        if severity:
            sev_clean = str(severity).lower().replace(" ", "_")
            tags.add(f"severity_{sev_clean}")
        
        # Inspection result
        result = record.get("establishment_status") or record.get("status") or record.get("Establishment Status")
        if result:
            tags.add(result.lower().replace(" ", "_"))
        
        # Causative agent (for outbreaks)
        agent = record.get("causative_agent_1") or record.get("Causative Agent-1")
        if agent and agent.lower() not in NULL_VALUES:
            tags.add(f"agent_{agent.lower().replace(' ', '_')}")
        
        return list(tags)
    # =========================================================================
    # NORMALIZATION HELPERS
    # =========================================================================
    
    
    def _normalize_value(self, field: str, value: Any) -> Any:
        """Normalize a value based on field type."""
        
        # Handle None
        if value is None:
            return None
        
        # Handle strings
        if isinstance(value, str):
            value = value.strip()
            
            # Check for null values
            if value.lower() in NULL_VALUES:
                return None
            
            # Boolean fields
            if field in BOOLEAN_FIELDS:
                return value.upper() in ("Y", "YES", "TRUE", "1", "ACTIVE")
        
        # Boolean conversion for non-strings
        if field in BOOLEAN_FIELDS:
            return bool(value)
        
        return value
    
    def _to_snake_case(self, name: str) -> str:
        """Convert field name to snake_case."""
        # Replace common separators
        name = name.replace("-", "_").replace(" ", "_")
        
        # Handle camelCase
        name = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
        
        # Clean up multiple underscores
        name = re.sub(r'_+', '_', name)
        
        return name.lower().strip("_")
    
    # =========================================================================
    # REPROCESSING
    # =========================================================================
    
    def reprocess_from_bronze(
        self,
        bronze_layer,
        dataset_id: str = None,
        metadata: Dict = None,
        batch_size: int = 1000
    ) -> Dict[str, int]:
        """
        Reprocess Silver from Bronze layer.
        
        Use when normalization rules change!
        
        Args:
            bronze_layer: BronzeLayer instance
            dataset_id: Dataset to reprocess (None = all)
            metadata: Metadata to apply
            batch_size: Batch size for processing
            
        Returns:
            Stats dict
        """
        stats = {"processed": 0, "errors": 0}
        batch = []
        # current_dataset = dataset_id
        
        # Iterate through Bronze records
        datasets = [dataset_id] if dataset_id else bronze_layer.get_datasets()
        
        for ds_id in datasets:
            print(f"  Reprocessing dataset: {ds_id}")
            
            for record in bronze_layer.iterate_dataset(ds_id, batch_size):
                try:
                    original = record.get("_original", record)
                    batch.append(original)
                    
                    if len(batch) >= batch_size:
                        result = self.store_batch(batch, ds_id, metadata)
                        stats["processed"] += result.get("stored", 0)
                        batch = []
                        
                except Exception as e:
                    print(f"    Error processing {e}")
                    stats["errors"] += 1
            
            # Process remaining
            if batch:
                result = self.store_batch(batch, ds_id, metadata)
                stats["processed"] += result.get("stored", 0)
                batch = []
        
        return stats
    
   
    # =========================================================================
    # RETRIEVAL
    # =========================================================================
    
    def get(self, unique_id: str) -> Optional[Dict]:
        """Get a record by unique ID."""
        return self.collection.find_one({"_unique_id": unique_id})
    
    def get_by_dataset(
        self,
        dataset_id: str,
        limit: int = None,
        skip: int = 0
    ) -> List[Dict]:
        """Get all records for a dataset."""
        cursor = self.collection.find(
            {"dataset_id": dataset_id}
        ).skip(skip)
        
        if limit:
            cursor = cursor.limit(limit)
        
        return list(cursor)
    
    def search(self, query: str, limit: int = 100) -> List[Dict]:
        """Full-text search on searchable_text."""
        return list(
            self.collection.find(
                {"$text": {"$search": query}},
                {"score": {"$meta": "textScore"}}
            ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        )
    
    def iterate_dataset(self, dataset_id: str, batch_size: int = 1000):
        """
        Iterate through all records in a dataset.
        
        Yields:
            Record documents
        """
        cursor = self.collection.find(
            {"dataset_id": dataset_id}
        ).batch_size(batch_size)
        
        for doc in cursor:
            yield doc
    
    # =========================================================================
    # UTILITIES
    # =========================================================================
    def _generate_id(self, record: Dict, dataset_id: str, resource_scope: str = "") -> str:
        """Generate unique ID for a record, scoped by resource to avoid collisions."""
        scope = resource_scope or "unknown_resource"

        record_id = record.get("_id") or record.get("id") or record.get("original_id")
        if record_id is not None:
            return f"{dataset_id}:{scope}:{record_id}"

        content = json.dumps(record, sort_keys=True, default=str)
        hash_id = hashlib.md5(content.encode()).hexdigest()[:12]
        return f"{dataset_id}:{scope}:{hash_id}"

    # def _generate_id(self, record: Dict, dataset_id: str) -> str:
    #     """Generate unique ID for a record."""
    #     record_id = record.get("_id") or record.get("id")
        
    #     if record_id is not None:
    #         return f"{dataset_id}_{record_id}"
        
    #     content = json.dumps(record, sort_keys=True, default=str)
    #     hash_id = hashlib.md5(content.encode()).hexdigest()[:12]
    #     return f"{dataset_id}_{hash_id}"
    
    def count(self, dataset_id: str = None) -> int:
        """Count records, optionally filtered by dataset."""
        query = {"dataset_id": dataset_id} if dataset_id else {}
        return self.collection.count_documents(query)
    
    def get_datasets(self) -> List[str]:
        """Get list of all dataset IDs."""
        return self.collection.distinct("dataset_id")
    
    def delete_dataset(self, dataset_id: str) -> int:
        """Delete all records for a dataset."""
        result = self.collection.delete_many({"dataset_id": dataset_id})
        return result.deleted_count
    
    def add_field_mapping(self, original: str, normalized: str):
        """Add a custom field mapping."""
        self.field_map[original] = normalized




# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_silver_instance: Optional[SilverLayer] = None


def get_silver(**kwargs) -> SilverLayer:
    """Get singleton Silver Layer instance."""
    global _silver_instance
    if _silver_instance is None:
        _silver_instance = SilverLayer(**kwargs)
    return _silver_instance


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "SilverLayer",
    "get_silver",
]