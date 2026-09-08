"""
Incremental Sync Manager

Tracks what's been indexed and only syncs new/changed documents.
Supports multiple indices with different mappings.

Key Features:
- Tracks last sync timestamp per dataset
- Only indexes new documents since last sync
- Handles failures with resume capability
- Supports multiple ES indices
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from pathlib import Path
import sys
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum




SCRIPT_DIR = Path(__file__).resolve().parent      # ES/
OPENDATA_DIR = SCRIPT_DIR.parent                  # OpenData/
SCRIPT_ROOT = OPENDATA_DIR.parent                 # script/
PROJECT_ROOT = SCRIPT_ROOT.parent                 # HOLA-dashboard/

# Add project root to path (where utils folder lives)
sys.path.insert(0, str(PROJECT_ROOT))

from pymongo import MongoClient
from pymongo.collection import Collection
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk

logger = logging.getLogger(__name__)

# ============================================================================
# IMPORT THE MAPPING
# ============================================================================
try:
    from es_policy_mapping import POLICY_RECORDS_MAPPING
except ImportError:
    # Fallback if import fails
    POLICY_RECORDS_MAPPING = None

logger = logging.getLogger(__name__)

from utils import get_mongodb_uri
# ============================================================================
# CONFIGURATION
# ============================================================================

class SyncStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some docs failed


@dataclass
class SyncResult:
    dataset_id: str
    status: SyncStatus
    documents_found: int = 0
    documents_indexed: int = 0
    documents_failed: int = 0
    documents_skipped: int = 0
    started_at: datetime = None
    completed_at: datetime = None
    error: str = None
    last_indexed_id: str = None


# ============================================================================
# SYNC STATE STORAGE (MongoDB)
# ============================================================================

class SyncStateManager:
    """
    Tracks sync state in MongoDB.
    
    Stores:
    - Last sync timestamp per dataset
    - Last indexed document ID
    - Sync history
    """
    
    def __init__(self, db):
        self.state_collection: Collection = db["_sync_state"]
        self.history_collection: Collection = db["_sync_history"]
        
        # Ensure indexes
        self.state_collection.create_index("dataset_id", unique=True)
        self.history_collection.create_index([("dataset_id", 1), ("started_at", -1)])
    
    def get_last_sync(self, dataset_id: str) -> Optional[Dict]:
        """Get last sync info for a dataset."""
        return self.state_collection.find_one({"dataset_id": dataset_id})
    
    def get_last_sync_time(self, dataset_id: str) -> Optional[datetime]:
        """Get timestamp of last successful sync."""
        state = self.get_last_sync(dataset_id)
        if state and state.get("status") == "completed":
            return state.get("last_sync_at")
        return None
    
    def get_last_indexed_id(self, dataset_id: str) -> Optional[str]:
        """Get the last indexed document ID (for resume)."""
        state = self.get_last_sync(dataset_id)
        return state.get("last_indexed_id") if state else None
    
    def start_sync(self, dataset_id: str) -> str:
        """Mark sync as started, return sync_id."""
        sync_id = f"{dataset_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        self.state_collection.update_one(
            {"dataset_id": dataset_id},
            {
                "$set": {
                    "dataset_id": dataset_id,
                    "status": "in_progress",
                    "current_sync_id": sync_id,
                    "started_at": datetime.now(timezone.utc),
                }
            },
            upsert=True
        )
        
        # Add to history
        self.history_collection.insert_one({
            "sync_id": sync_id,
            "dataset_id": dataset_id,
            "status": "in_progress",
            "started_at": datetime.now(timezone.utc),
        })
        
        return sync_id
    
    def update_progress(self, dataset_id: str, last_indexed_id: str, indexed_count: int):
        """Update sync progress (for resume capability)."""
        self.state_collection.update_one(
            {"dataset_id": dataset_id},
            {
                "$set": {
                    "last_indexed_id": last_indexed_id,
                    "documents_indexed": indexed_count,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
    
    def complete_sync(self, dataset_id: str, result: SyncResult):
        """Mark sync as completed."""
        now = datetime.now(timezone.utc)
        
        self.state_collection.update_one(
            {"dataset_id": dataset_id},
            {
                "$set": {
                    "status": result.status.value,
                    "last_sync_at": now,
                    "last_indexed_id": result.last_indexed_id,
                    "documents_indexed": result.documents_indexed,
                    "documents_failed": result.documents_failed,
                    "completed_at": now,
                    "error": result.error,
                }
            }
        )
        
        # Update history
        self.history_collection.update_one(
            {"sync_id": self.state_collection.find_one({"dataset_id": dataset_id}).get("current_sync_id")},
            {
                "$set": {
                    "status": result.status.value,
                    "completed_at": now,
                    "documents_indexed": result.documents_indexed,
                    "documents_failed": result.documents_failed,
                    "error": result.error,
                }
            }
        )
    
    def get_all_states(self) -> List[Dict]:
        """Get sync state for all datasets."""
        return list(self.state_collection.find())


# ============================================================================
# INCREMENTAL SYNC MANAGER
# ============================================================================

class IncrementalSyncManager:
    """
    Manages incremental sync from MongoDB to Elasticsearch.
    
    Only syncs documents that are new or changed since last sync.
    """
    
    def __init__(
        self,
        mongo_uri: str = None,
        mongo_database: str = "policy_issues",
        es_hosts: List[str] = None,
        es_username: str = None,
        es_password: str = None,
        batch_size: int = 200,
    ):
        # MongoDB
        mongo_uri = mongo_uri or get_mongodb_uri()
        self.mongo = MongoClient(mongo_uri)
        self.db = self.mongo[mongo_database]
        
        # Sync state manager
        self.state_manager = SyncStateManager(self.db)
        
        # Elasticsearch
        es_kwargs = {
            'hosts': es_hosts or ['https://localhost:9200'],
            'verify_certs': False,
            'ssl_show_warn': False,
            'request_timeout': 120,
            'retry_on_timeout': True,
            'max_retries': 3,
        }
        if es_username and es_password:
            es_kwargs['basic_auth'] = (es_username, es_password)
        
        self.es = Elasticsearch(**es_kwargs)
        self.batch_size = batch_size
        
        logger.info(f"IncrementalSyncManager initialized")
    
    # =========================================================================
    # INCREMENTAL SYNC
    # =========================================================================
    
    def sync_dataset(
        self,
        dataset_id: str,
        source_collection: str,
        es_index: str,
        doc_transformer: callable = None,
        force_full: bool = False,
        resume: bool = True,
    ) -> SyncResult:
        """
        Incrementally sync a dataset from MongoDB to Elasticsearch.
        
        Args:
            dataset_id: Unique identifier for this dataset
            source_collection: MongoDB collection name
            es_index: Elasticsearch index name
            doc_transformer: Function to transform MongoDB doc to ES doc
            force_full: Force full re-sync (ignore last sync time)
            resume: Resume from last indexed ID if previous sync failed
            
        Returns:
            SyncResult with status and counts
        """
        result = SyncResult(
            dataset_id=dataset_id,
            status=SyncStatus.PENDING,
            started_at=datetime.now(timezone.utc)
        )
        
        try:
            # Get source collection
            collection = self.db[source_collection]
            print(f"Source collection: {source_collection}")
            count = collection.count_documents({})
            print(f"Total documents in source collection '{source_collection}': {count}")
            
            # Determine what to sync
            query = self._build_incremental_query(dataset_id, force_full, resume)
            
            query["dataset_id"] = dataset_id

            # Count documents to sync
            result.documents_found = collection.count_documents(query)
            
            if result.documents_found == 0:
                logger.info(f"[{dataset_id}] No new documents to sync")
                result.status = SyncStatus.COMPLETED
                result.completed_at = datetime.now(timezone.utc)
                return result
            
            logger.info(f"[{dataset_id}] Found {result.documents_found} documents to sync")
            
            # Start sync
            sync_id = self.state_manager.start_sync(dataset_id)
            result.status = SyncStatus.IN_PROGRESS
            
            # Ensure index exists
            self._ensure_index(es_index)
            
            # Sync documents
            success, failed, last_id = self._bulk_index(
                collection=collection,
                query=query,
                es_index=es_index,
                dataset_id=dataset_id,
                doc_transformer=doc_transformer,
            )
            
            result.documents_indexed = success
            result.documents_failed = failed
            result.last_indexed_id = last_id
            
            # Determine final status
            if failed == 0:
                result.status = SyncStatus.COMPLETED
            elif success > 0:
                result.status = SyncStatus.PARTIAL
            else:
                result.status = SyncStatus.FAILED
            
            result.completed_at = datetime.now(timezone.utc)
            
            # Save state
            self.state_manager.complete_sync(dataset_id, result)
            
            logger.info(f"[{dataset_id}] Sync complete: {success} indexed, {failed} failed")
            
        except Exception as e:
            logger.error(f"[{dataset_id}] Sync failed: {e}")
            result.status = SyncStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now(timezone.utc)
            self.state_manager.complete_sync(dataset_id, result)
        
        return result
    
    def _build_incremental_query(
        self,
        dataset_id: str,
        force_full: bool,
        resume: bool
    ) -> Dict:
        """Build MongoDB query for incremental sync."""
        
        if force_full:
            logger.info(f"[{dataset_id}] Force full sync - no filters")
            return {}
        
        query_parts = []
        
        # Get last sync time
        last_sync = self.state_manager.get_last_sync_time(dataset_id)
        
        if last_sync:
            # Only get documents created/modified after last sync
            query_parts.append({
                "$or": [
                    {"_created_at": {"$gt": last_sync}},
                    {"_updated_at": {"$gt": last_sync}},
                    {"_ingested_at": {"$gt": last_sync}},  # Fallback field
                ]
            })
            logger.info(f"[{dataset_id}] Incremental sync from {last_sync}")
        
        # Resume from last indexed ID if previous sync failed
        if resume:
            last_state = self.state_manager.get_last_sync(dataset_id)
            if last_state and last_state.get("status") == "in_progress":
                last_id = last_state.get("last_indexed_id")
                if last_id:
                    query_parts.append({"_id": {"$gt": last_id}})
                    logger.info(f"[{dataset_id}] Resuming from ID: {last_id}")
        
        if query_parts:
            return {"$and": query_parts} if len(query_parts) > 1 else query_parts[0]
        
        return {}
    
    # =========================================================================
    # FIXED: _ensure_index NOW APPLIES PROPER MAPPING
    # =========================================================================
    
    def _ensure_index(self, es_index: str):
        """Ensure ES index exists with proper mapping."""
        if not self.es.indices.exists(index=es_index):
            if POLICY_RECORDS_MAPPING:
                self.es.indices.create(index=es_index, body=POLICY_RECORDS_MAPPING)
                logger.info(f"✅ Created ES index '{es_index}' WITH POLICY_RECORDS_MAPPING")
            else:
                # Fallback to basic settings if mapping not available
                self.es.indices.create(index=es_index, body={
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                    }
                })
                logger.warning(f"⚠️ Created ES index '{es_index}' WITHOUT mapping (POLICY_RECORDS_MAPPING not found)")
        else:
            logger.info(f"Index '{es_index}' already exists")
    
    def _bulk_index(
        self,
        collection: Collection,
        query: Dict,
        es_index: str,
        dataset_id: str,
        doc_transformer: callable = None,
    ) -> tuple:
        """Bulk index documents to Elasticsearch."""
        
        success = 0
        failed = 0
        last_id = None
        errors = []
        
        def generate_actions():
            nonlocal last_id
            
            # Sort by _id for consistent ordering (important for resume)
            cursor = collection.find(query).sort("_id", 1)
            
            for doc in cursor:
                # Transform document
                if doc_transformer:
                    es_doc = doc_transformer(doc)
                else:
                    es_doc = self._default_transform(doc)
                
                # Get unique ID
                doc_id = es_doc.get("_unique_id") or str(doc.get("_id"))
                last_id = doc_id
                
                yield {
                    "_index": es_index,
                    "_id": doc_id,
                    "_source": es_doc,
                }
        
        try:
            for ok, result in streaming_bulk(
                self.es,
                generate_actions(),
                chunk_size=self.batch_size,
                raise_on_error=False,
                raise_on_exception=False,
                max_retries=3,
            ):
                if ok:
                    success += 1
                    
                    # Update progress periodically
                    if success % 1000 == 0:
                        self.state_manager.update_progress(dataset_id, last_id, success)
                        logger.info(f"[{dataset_id}] Progress: {success} indexed")
                else:
                    failed += 1
                    if len(errors) < 10:
                        errors.append(str(result))
            
            if errors:
                logger.error(f"[{dataset_id}] Errors: {errors[:5]}")
                
        except Exception as e:
            logger.error(f"[{dataset_id}] Bulk index error: {e}")
            errors.append(str(e))
        
        # Refresh index
        try:
            self.es.indices.refresh(index=es_index)
        except:
            pass
        
        return success, failed, last_id
    
    def _default_transform(self, doc: Dict) -> Dict:
        """Default document transformation."""
        es_doc = dict(doc)
        
        # Remove MongoDB _id (ES uses _unique_id)
        es_doc.pop("_id", None)
        
        # Ensure _unique_id exists
        if "_unique_id" not in es_doc:
            es_doc["_unique_id"] = str(doc.get("_id"))
        
        return es_doc
    
    # =========================================================================
    # MULTI-DATASET SYNC
    # =========================================================================
    
    def sync_all(
        self,
        datasets: List[Dict],
        force_full: bool = False,
    ) -> Dict[str, SyncResult]:
        """
        Sync multiple datasets.
        
        Args:
            datasets: List of dataset configs:
                [
                    {
                        "dataset_id": "policy_issues",
                        "source_collection": "policy_datas",
                        "es_index": "policy_issues_toronto",
                        "transformer": optional_function,
                    },
                    ...
                ]
            force_full: Force full re-sync for all
            
        Returns:
            Dict of dataset_id -> SyncResult
        """
        results = {}
        
        for ds in datasets:
            result = self.sync_dataset(
                dataset_id=ds["dataset_id"],
                source_collection=ds["source_collection"],
                es_index=ds["es_index"],
                doc_transformer=ds.get("transformer"),
                force_full=force_full,
            )
            results[ds["dataset_id"]] = result
        
        return results
    
    def sync_by_category(
        self,
        category: str,
        source_collection: str = "policy_datas",
        es_index: str = "policy_issues_toronto",
        force_full: bool = False,
    ) -> SyncResult:
        """Sync documents matching a specific category."""
        
        # This syncs all documents with matching category
        # Uses category as part of the dataset_id for separate tracking
        dataset_id = f"{es_index}_{category}"
        
        # Custom query includes category filter
        collection = self.db[source_collection]
        
        # Get incremental query
        base_query = self._build_incremental_query(dataset_id, force_full, True)
        
        # Add category filter
        if base_query:
            query = {"$and": [base_query, {"primary_issue": category}]}
        else:
            query = {"primary_issue": category}
        
        # Count
        count = collection.count_documents(query)
        logger.info(f"[{dataset_id}] Found {count} documents for category '{category}'")
        
        if count == 0:
            return SyncResult(
                dataset_id=dataset_id,
                status=SyncStatus.COMPLETED,
                documents_found=0,
            )
        
        # Sync
        return self.sync_dataset(
            dataset_id=dataset_id,
            source_collection=source_collection,
            es_index=es_index,
            force_full=force_full,
        )
    
    # =========================================================================
    # STATUS & MONITORING
    # =========================================================================
    
    def get_sync_status(self, dataset_id: str = None) -> Dict:
        """Get sync status for one or all datasets."""
        
        if dataset_id:
            state = self.state_manager.get_last_sync(dataset_id)
            return state or {"dataset_id": dataset_id, "status": "never_synced"}
        
        # All datasets
        states = self.state_manager.get_all_states()
        return {s["dataset_id"]: s for s in states}
    
    def get_sync_gap(self, source_collection: str, es_index: str) -> Dict:
        """Compare document counts between MongoDB and ES."""
        
        mongo_count = self.db[source_collection].count_documents({})
        
        try:
            es_count = self.es.count(index=es_index)["count"]
        except:
            es_count = 0
        
        return {
            "mongodb_count": mongo_count,
            "elasticsearch_count": es_count,
            "gap": mongo_count - es_count,
        }

# =========================================================================
    # INDEX MANAGEMENT
    # =========================================================================
    
    def delete_and_recreate_index(self, es_index: str) -> bool:
        """
        Delete an existing index and recreate it with proper mapping.
        Use this to fix mapping issues.
        """
        try:
            # Delete if exists
            if self.es.indices.exists(index=es_index):
                self.es.indices.delete(index=es_index)
                logger.info(f"🗑️ Deleted index: {es_index}")
            
            # Create with mapping
            if POLICY_RECORDS_MAPPING:
                self.es.indices.create(index=es_index, body=POLICY_RECORDS_MAPPING)
                logger.info(f"✅ Created index '{es_index}' with POLICY_RECORDS_MAPPING")
            else:
                logger.error("❌ POLICY_RECORDS_MAPPING not available!")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to recreate index: {e}")
            return False


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_sync_manager(
    mongo_uri: str = None,
    mongo_database: str = None,
    es_config: Dict = None,
) -> IncrementalSyncManager:
    """Create sync manager with config."""
    
    # Default values or from environment
    import os
    
    mongo_uri = mongo_uri or get_mongodb_uri()
    print("Using Mongo URI from sync:", mongo_uri)
    mongo_database = mongo_database or os.getenv("MONGO_DATABASE", "policy_issues")
    
    es_config = es_config or {
        "hosts": [os.getenv("ELASTICSEARCH_HOSTS", "https://localhost:9200")],
        "username": os.getenv("ELASTICSEARCH_USERNAME"),
        "password": os.getenv("ELASTICSEARCH_PASSWORD"),
    }
    
    return IncrementalSyncManager(
        mongo_uri=mongo_uri,
        mongo_database=mongo_database,
        es_hosts=es_config.get("hosts"),
        es_username=es_config.get("username"),
        es_password=es_config.get("password"),
    )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    """
    Example: Incremental sync of policy data
    
    Day 1: 120,000 documents synced
    Day 2: Only new 20,000 documents synced (140k - 120k)
    Day 3: Only new 5,000 documents synced
    """
    
    # Setup
    sync = create_sync_manager()

    print("Recreating index with proper mapping...")
    sync.delete_and_recreate_index("policy_issues_toronto")
    
    # Sync policy issues (incremental - only new docs)
    result = sync.sync_dataset(
        dataset_id="policy_issues",
        source_collection="policy_datas",
        es_index="policy_issues_toronto",
    )
    
    print(f"Synced {result.documents_indexed} new documents")
    print(f"Status: {result.status.value}")
    
    # Check gap
    gap = sync.get_sync_gap("policy_datas", "policy_issues_toronto")
    print(f"MongoDB: {gap['mongodb_count']}, ES: {gap['elasticsearch_count']}, Gap: {gap['gap']}")
    
    # Force full re-sync if needed
    # result = sync.sync_dataset(..., force_full=True)