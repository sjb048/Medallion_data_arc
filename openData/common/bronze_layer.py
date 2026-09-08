# bronze_layer.py
"""
BRONZE LAYER - Raw Data Storage

Stores data EXACTLY as received with NO transformation.
Purpose: Audit trail, reprocessing capability, data lineage.

MongoDB Collection: raw_records

Usage:
    from bronze_layer import BronzeLayer
    
    bronze = BronzeLayer()
    bronze.store(record, dataset_id="outbreaks")
    bronze.store_batch(records, dataset_id="outbreaks")
"""

import json
import os
import sys
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection
from pathlib import Path
from starlette.middleware.trustedhost import TrustedHostMiddleware



class BronzeLayer:
    """
    Bronze Layer: Raw data storage.
    
    NO TRANSFORMATION - stores data exactly as received!
    
    Schema:
        {
            "_raw_id": "dataset_recordid",      # Unique identifier
            "_dataset_id": "outbreaks",         # Source dataset
            "_source_file": "outbreaks.json",   # Original file (optional)
            "_loaded_at": datetime,             # When loaded
            "_checksum": "md5hash",             # Data integrity check
            "_original": { ... }                # RAW DATA - NO CHANGES!
        }
    """
    
    COLLECTION_NAME = "raw_records"
    
    def __init__(
        self,
        mongo_uri:str = None,
        database: str = "policy_issues",
        collection: str = None
    ):
        """
        Initialize Bronze Layer.
        
        Args:
            mongo_uri: MongoDB connection string
            database: Database name
            collection: Collection name (default: raw_records)
        """
        self.client = MongoClient(mongo_uri)
        print("BronzeLayer using Mongo URI:", mongo_uri)

        self.db = self.client[database]
        self.collection: Collection = self.db[collection or self.COLLECTION_NAME]
        
        # Create indexes
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create indexes for efficient queries."""
        self.collection.create_index("_raw_id", unique=True)
        self.collection.create_index("_dataset_id")
        self.collection.create_index("_loaded_at")
        self.collection.create_index("_checksum")
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def store(
        self,
        record: Dict,
        dataset_id: str,
        source_file: str = None,
        extra_metadata: Dict = None
    ) -> str:
        """
        Store a single raw record.
        
        Args:
            record: Raw record (NO transformation applied)
            dataset_id: Dataset identifier (e.g., "outbreaks")
            source_file: Original source file name
            extra_metadata: Additional metadata to store
            
        Returns:
            The _raw_id of the stored record
        """
        raw_id = self._generate_id(record, dataset_id, source_scope=source_file)
        checksum = self._compute_checksum(record)
        
        doc = {
            "_raw_id": raw_id,
            "_dataset_id": dataset_id,
            "_source_file": source_file,
            "_loaded_at": datetime.utcnow(),
            "_checksum": checksum,
            "_original": record  # <-- RAW DATA, NO CHANGES!
        }
        
        # Add extra metadata if provided
        if extra_metadata:
            doc["_extra"] = extra_metadata
        
        self.collection.update_one(
            {"_raw_id": raw_id},
            {"$set": doc},
            upsert=True
        )
        
        return raw_id
    
    def store_batch(
        self,
        records: List[Dict],
        dataset_id: str,
        source_file: str = None,
        extra_metadata: Dict = None
    ) -> Dict[str, int]:
        """
        Store multiple raw records efficiently.
        
        Args:
            records: List of raw records
            dataset_id: Dataset identifier
            source_file: Original source file name
            extra_metadata: Additional metadata to store
            
        Returns:
            Stats dict with counts
        """
        if not records:
            return {"stored": 0, "errors": 0}
        
        operations = []
        timestamp = datetime.utcnow()
        
        for record in records:
            raw_id = self._generate_id(record, dataset_id, source_scope=source_file)
            checksum = self._compute_checksum(record)
            
            doc = {
                "_raw_id": raw_id,
                "_dataset_id": dataset_id,
                "_source_file": source_file,
                "_loaded_at": timestamp,
                "_checksum": checksum,
                "_original": record
            }
            
            if extra_metadata:
                doc["_extra"] = extra_metadata
            
            operations.append(
                UpdateOne(
                    {"_raw_id": raw_id},
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
    
    # =========================================================================
    # RETRIEVAL
    # =========================================================================
    
    def get(self, raw_id: str) -> Optional[Dict]:
        """Get a raw record by ID."""
        doc = self.collection.find_one({"_raw_id": raw_id})
        return doc.get("_original") if doc else None
    
    def get_by_dataset(
        self,
        dataset_id: str,
        limit: int = None,
        skip: int = 0
    ) -> List[Dict]:
        """
        Get all raw records for a dataset.
        
        Args:
            dataset_id: Dataset identifier
            limit: Maximum records to return
            skip: Records to skip (for pagination)
            
        Returns:
            List of raw records (just the _original data)
        """
        cursor = self.collection.find(
            {"_dataset_id": dataset_id},
            {"_original": 1, "_raw_id": 1}
        ).skip(skip)
        
        if limit:
            cursor = cursor.limit(limit)
        
        return [
            {**doc["_original"], "_raw_id": doc["_raw_id"]}
            for doc in cursor
        ]
    
    def iterate_dataset(self, dataset_id: str, batch_size: int = 1000):
        """
        Iterate through all records in a dataset.
        
        Yields:
            Tuple of (raw_id, original_record)
        """
        cursor = self.collection.find(
            {"_dataset_id": dataset_id},
            {"_original": 1, "_raw_id": 1}
        ).batch_size(batch_size)
        
        for doc in cursor:
            yield doc["_raw_id"], doc["_original"]
    
    # =========================================================================
    # UTILITIES
    # =========================================================================
    def _generate_id(self, record: Dict, dataset_id: str, source_scope: str = "") -> str:
        """Generate unique ID for a record, scoped by resource/file to avoid collisions."""
        scope = source_scope or "unknown_source"

        record_id = record.get("_id") or record.get("id") or record.get("original_id")
        if record_id is not None:
            return f"{dataset_id}:{scope}:{record_id}"

        # Hash content for ID (still scoped)
        content = json.dumps(record, sort_keys=True, default=str)
        hash_id = hashlib.md5(content.encode()).hexdigest()[:12]
        return f"{dataset_id}:{scope}:{hash_id}"

    # def _generate_id(self, record: Dict, dataset_id: str) -> str:
    #     """Generate unique ID for a record."""
    #     # Try to use existing ID
    #     record_id = record.get("_id") or record.get("id")
        
    #     if record_id is not None:
    #         return f"{dataset_id}_{record_id}"
        
    #     # Hash content for ID
    #     content = json.dumps(record, sort_keys=True, default=str)
    #     hash_id = hashlib.md5(content.encode()).hexdigest()[:12]
    #     return f"{dataset_id}_{hash_id}"
    
    def _compute_checksum(self, record: Dict) -> str:
        """Compute MD5 checksum of record for integrity checking."""
        content = json.dumps(record, sort_keys=True, default=str)
        return hashlib.md5(content.encode()).hexdigest()
    
    def count(self, dataset_id: str = None) -> int:
        """Count records, optionally filtered by dataset."""
        query = {"_dataset_id": dataset_id} if dataset_id else {}
        return self.collection.count_documents(query)
    
    def get_datasets(self) -> List[str]:
        """Get list of all dataset IDs."""
        return self.collection.distinct("_dataset_id")
    
    def delete_dataset(self, dataset_id: str) -> int:
        """Delete all records for a dataset."""
        result = self.collection.delete_many({"_dataset_id": dataset_id})
        return result.deleted_count
    
    def verify_integrity(self, dataset_id: str = None) -> Dict:
        """
        Verify data integrity by checking checksums.
        
        Returns:
            Dict with valid/invalid counts
        """
        query = {"_dataset_id": dataset_id} if dataset_id else {}
        
        stats = {"valid": 0, "invalid": 0, "invalid_ids": []}
        
        for doc in self.collection.find(query):
            stored_checksum = doc.get("_checksum")
            current_checksum = self._compute_checksum(doc.get("_original", {}))
            
            if stored_checksum == current_checksum:
                stats["valid"] += 1
            else:
                stats["invalid"] += 1
                stats["invalid_ids"].append(doc["_raw_id"])
        
        return stats


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_bronze_instance: Optional[BronzeLayer] = None


def get_bronze(**kwargs) -> BronzeLayer:
    """Get singleton Bronze Layer instance."""
    global _bronze_instance
    if _bronze_instance is None:
        _bronze_instance = BronzeLayer(**kwargs)
    return _bronze_instance


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "BronzeLayer",
    "get_bronze",
]