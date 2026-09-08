# =============================================================================

import logging
import urllib3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Generator, Set
from dataclasses import dataclass, field, asdict
from enum import Enum

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk



from .es_config import (
    ES_CONFIG, DEFAULT_ES_INDEX, 
    DEFAULT_MONGO_URI, DEFAULT_MONGO_DATABASE,
    DEFAULT_SILVER_COLLECTION, DEFAULT_BATCH_SIZE
)
from .es_doc import get_doc_id, prepare_es_document

# Suppress SSL warnings if configured
if not ES_CONFIG.get('ssl_show_warn', True):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


logger = logging.getLogger(__name__)

def create_es_client(es_config: Dict = None) -> Elasticsearch:
    """Create Elasticsearch client from config dict."""
    config = es_config or ES_CONFIG
    
    hosts = config.get('hosts', ['http://localhost:9200'])
    username = config.get('username')
    password = config.get('password')
    
    es_kwargs = {
        'hosts': hosts,
        'verify_certs': config.get('verify_certs', False),
        'ssl_show_warn': config.get('ssl_show_warn', False),
        'timeout': config.get('timeout', 120),  # Increased to 120 seconds
        'max_retries': 3,
        'retry_on_timeout': True,
    }
    
    if username and password:
        es_kwargs['basic_auth'] = (username, password)
    
    return Elasticsearch(**es_kwargs)

# =============================================================================
# DATA CLASSES
# =============================================================================


class SyncStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

@dataclass
class SyncState:
    """Tracks sync state for a dataset or category."""

    dataset_id: str
    last_synced_at: datetime = None
    last_mongo_timestamp: datetime = None
    documents_synced: int = 0
    documents_failed: int = 0
    status: SyncStatus = SyncStatus.PENDING
    error_message: str = None
    sync_duration_ms: int = 0
    checksum: str = None  # For detecting mapping changes
    
    def to_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "last_synced_at": self.last_synced_at,
            "last_mongo_timestamp": self.last_mongo_timestamp,
            "documents_synced": self.documents_synced,
            "documents_failed": self.documents_failed,
            "status": self.status.value,
            "error_message": self.error_message,
            "sync_duration_ms": self.sync_duration_ms,
            "checksum": self.checksum,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SyncState":
        if data is None:
            return None
        return cls(
            dataset_id=data["dataset_id"],
            last_synced_at=data.get("last_synced_at"),
            last_mongo_timestamp=data.get("last_mongo_timestamp"),
            documents_synced=data.get("documents_synced", 0),
            documents_failed=data.get("documents_failed", 0),
            status=SyncStatus(data.get("status", "pending")),
            error_message=data.get("error_message"),
            sync_duration_ms=data.get("sync_duration_ms", 0),
            checksum=data.get("checksum"),
        )


@dataclass
class SyncResult:
    """Result of a sync operation."""

    dataset_id: str
    started_at: datetime
    completed_at: datetime = None
    documents_processed: int = 0
    documents_indexed: int = 0
    documents_updated: int = 0
    documents_failed: int = 0
    errors: List[str] = field(default_factory=list)
    status: SyncStatus = SyncStatus.PENDING

# =============================================================================
# SYNC MANAGER
# =============================================================================

class SyncManager:
    """
    Manages incremental synchronization between MongoDB and Elasticsearch.
    
    Architecture:
        MongoDB (Silver) ──► SyncManager ──► Elasticsearch (Gold)
                                │
                                └── Sync State Collection (MongoDB)
    
    Sync Strategies:
        1. INCREMENTAL: Only sync documents newer than last sync
        2. DATASET: Sync all documents for a specific dataset
        3. CATEGORY: Sync all documents for a category (health, housing, etc.)
        4. FULL: Complete resync (use when mappings change)
    """

    SYNC_STATE_COLLECTION = "sync_state"
    SYNC_HISTORY_COLLECTION = "sync_history"
    
    def __init__(
        self,
        mongo_uri: str = DEFAULT_MONGO_URI,
        mongo_database: str = DEFAULT_MONGO_DATABASE,
        silver_collection: str = DEFAULT_SILVER_COLLECTION,
        es_config: Dict = None,
        es_index: str = DEFAULT_ES_INDEX,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self.mongo = MongoClient(mongo_uri)
        self.db = self.mongo[mongo_database]
        self.silver: Collection = self.db[silver_collection]
        
         # State collections
        self.sync_state = self.db[self.SYNC_STATE_COLLECTION]
        self.sync_history = self.db[self.SYNC_HISTORY_COLLECTION]
       
        # Elasticsearch with SSL settings
        self.es_config = es_config or ES_CONFIG
        self.es = create_es_client(self.es_config)
        self.es_index = es_index
        self.batch_size = batch_size
        
        # Ensure indexes
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create indexes for efficient sync queries."""
        # Compound index for pending items query
        self.silver.create_index([("loaded_at", ASCENDING)])
        self.silver.create_index([("dataset_id", ASCENDING)])
        self.silver.create_index([("dataset_id", ASCENDING), ("loaded_at", ASCENDING)])
        self.sync_state.create_index([("dataset_id", ASCENDING)], unique=True)
        self.sync_history.create_index([("dataset_id", ASCENDING), ("created_at", DESCENDING)])
    
    
    # =========================================================================
    # PUBLIC API - SYNC OPERATIONS
    # =========================================================================
    def incremental_sync(
        self,
        datasets: List[str] = None,
        categories: List[str] = None,
    ) -> Dict[str, SyncResult]:
        """
        Incrementally sync only new/changed documents.
        
        This is the RECOMMENDED method for regular sync operations.
        Only documents added/modified since the last sync are processed.
        
        Args:
            since: Override - sync documents since this time
            datasets: Limit to specific datasets (optional)
            categories: Limit to specific categories (optional)
            
        Returns:
            Dict of dataset_id → SyncResult
        """
        logger.info("Starting incremental sync...")
        results: Dict[str, SyncResult] = {}
        
        # Get list of datasets to sync
        target_datasets = self._get_target_datasets(datasets, categories)
        
        for dataset_id in target_datasets:
            # Get last sync state
            state = self._get_sync_state(dataset_id)
            
            since = state.last_mongo_timestamp if state else None
            results[dataset_id] = self._sync_dataset(dataset_id, since)
        
        logger.info(f"Incremental sync complete. Processed {len(results)} datasets.")
        return results
    
    def sync_dataset(
        self,
        dataset_id: str,
        force_full: bool = False,
    ) -> SyncResult:
        """
        Sync a specific dataset.
        
        Args:
            dataset_id: Dataset identifier
            force_full: If True, sync all documents (not just new ones)
            
        Returns:
            SyncResult
        """
        if force_full:
            self._delete_es_documents(dataset_id)
            return self._sync_dataset_full(dataset_id)
        
        state = self._get_sync_state(dataset_id)
        since = state.last_mongo_timestamp if state else None
        return self._sync_dataset(dataset_id, since)
    
    def sync_category(self, category: str, force_full: bool = False) -> Dict[str, SyncResult]:
        """Sync all datasets in a category."""
        datasets = self._get_datasets_by_category(category)
        return {ds: self.sync_dataset(ds, force_full) for ds in datasets}
    
    def sync_new_category_only(self, category: str) -> Dict[str, SyncResult]:
        """Sync only datasets that have never been synced."""

        datasets = self._get_datasets_by_category(category)
        results = {}
        
        for dataset_id in datasets:
            state = self._get_sync_state(dataset_id)
            
            # Skip if already synced
            if state and state.status == SyncStatus.COMPLETED:
                logger.info(f"Skipping {dataset_id} - already synced")
                continue
            
            results[dataset_id] = self._sync_dataset(dataset_id, since=None)
        
        return results

    
    def full_resync(self, datasets: List[str] = None, recreate_index: bool = False) -> Dict[str, SyncResult]:
        """Full resync - use when mappings change."""
        
        logger.warning("Starting FULL resync - this may take a while...")
        
        if recreate_index:
            self._recreate_es_index()
        
        target_datasets = datasets or self._get_all_datasets()
        results = {}
        
        for dataset_id in target_datasets:
            self._delete_es_documents(dataset_id)
            results[dataset_id] = self._sync_dataset(dataset_id, since=None)
        
        
        # Clear sync states for resynced datasets
        if datasets:
            self.sync_state.delete_many({"dataset_id": {"$in": datasets}})
        else:
            self.sync_state.delete_many({})
        
        return results
    
    
    # =========================================================================
    # SYNC IMPLEMENTATION
    # =========================================================================
    def _sync_dataset(self, dataset_id: str, since: datetime = None) -> SyncResult:
        """Core sync logic for a dataset."""
        result = SyncResult(dataset_id=dataset_id, started_at=datetime.utcnow())
        
        try:
            query = {"dataset_id": dataset_id}
            if since:
                query["$or"] = [
                    {"loaded_at": {"$gt": since}},
                    {"updated_at": {"$gt": since}},
                ]
            
            total = self.silver.count_documents(query)
            if total == 0:
                result.status = SyncStatus.COMPLETED
                result.completed_at = datetime.now(timezone.utc).isoformat()
                return result
            
            logger.info(f"Syncing {total} docs for {dataset_id}")
            
            # Bulk index
            indexed, failed, errors = self._bulk_index(
                self._stream_documents(query), dataset_id
            )
            
            result.documents_indexed = indexed
            result.documents_failed = failed
            result.documents_processed = indexed + failed
            result.errors = errors
            result.status = SyncStatus.COMPLETED if failed == 0 else SyncStatus.PARTIAL
            result.completed_at = datetime.now(timezone.utc).isoformat()
            logger.info(
                "Sync result for %s: indexed=%d failed=%d",
                dataset_id,
                indexed,
                failed,
            )

            self._update_sync_state(dataset_id, result)
            
        except Exception as e:
            logger.error(f"Sync failed for {dataset_id}: {e}")
            result.status = SyncStatus.FAILED
            result.errors.append(str(e))
            result.completed_at = datetime.now(timezone.utc).isoformat()
        
        return result
    
    def _stream_documents(self, query: dict) -> Generator[dict, None, None]:
        """Stream documents from MongoDB."""
        for doc in self.silver.find(query).batch_size(self.batch_size):
            yield doc
    
    def _bulk_index(self, documents: Generator, dataset_id: str) -> tuple:
        """Bulk index to Elasticsearch."""
        success, errors_count, errors = 0, 0, []
        
        def actions():
            for doc in documents:
                es_doc = prepare_es_document(doc, dataset_id)
                yield {
                    "_index": self.es_index,
                    "_id": get_doc_id(es_doc),
                    "_source": es_doc,
                }
        
        # Use smaller chunk size and longer timeout for reliability
        chunk_size = min(self.batch_size, 200)  # Cap at 200 docs per chunk
        
        try:
            for ok, result in streaming_bulk(
                self.es, 
                actions(),
                chunk_size=chunk_size,
                raise_on_error=False,
                raise_on_exception=False,
                request_timeout=120,  # 2 minutes per chunk
                max_retries=3,
                initial_backoff=2,
                max_backoff=60,
            ):
                if ok:
                    success += 1
                    # Log progress every 5000 docs
                    if success % 5000 == 0:
                        logger.info(f"  Progress: {success} docs indexed for {dataset_id}")
                else:
                    errors_count += 1
                    if len(errors) < 10:
                        errors.append(str(result))
                        
        except Exception as e:
            logger.error(f"Bulk index exception: {e}")
            errors.append(str(e))
        
        if errors:
            logger.error("Bulk index errors (showing up to 10): %r", errors)

        try:
            self.es.indices.refresh(index=self.es_index)
        except Exception as e:
            logger.warning(f"Index refresh failed: {e}")
            
        return success, errors_count, [str(e) for e in errors]
    
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    def _get_sync_state(self, dataset_id: str) -> Optional[SyncState]:
        """Get sync state for a dataset."""
        doc = self.sync_state.find_one({"dataset_id": dataset_id})
        return SyncState.from_dict(doc) if doc else None
    
    def _update_sync_state(self, dataset_id: str, result: SyncResult):
        """Update sync state after sync operation."""
        # Get latest timestamp from MongoDB
        latest = self.silver.find_one(
            {"dataset_id": dataset_id},
            sort=[("loaded_at", DESCENDING)]
        )
        latest_ts = latest.get("loaded_at") if latest else None
        
        state = SyncState(
            dataset_id=dataset_id,
            last_synced_at=result.completed_at,
            last_mongo_timestamp=latest_ts,
            documents_synced=result.documents_indexed,
            documents_failed=result.documents_failed,
            status=result.status,
            error_message=result.errors[0] if result.errors else None,
            
        )
        
        self.sync_state.update_one(
            {"dataset_id": dataset_id},
            {"$set": state.to_dict()},
            upsert=True
        )
        
        # Also log to history
        self.sync_history.insert_one({
            **state.to_dict(),
            "sync_type": "incremental",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    
    
   
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _get_all_datasets(self) -> List[str]:
        """Get all unique dataset IDs from MongoDB."""
        return self.silver.distinct("dataset_id")
    
    def _get_datasets_by_category(self, category: str) -> List[str]:
        """Get dataset IDs for a category."""
        return self.silver.distinct(
            "dataset_id",
            {"primary_issue": category}
        )
    
    def _get_target_datasets(self, datasets: List[str], categories: List[str]) -> List[str]:
        """Get list of datasets to sync based on filters."""
        if datasets:
            return datasets
        
        if categories:
            result = set()
            for cat in categories:
                result.update(self._get_datasets_by_category(cat))
            return list(result)
        
        return self._get_all_datasets()
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get overall sync status."""
        states = list(self.sync_state.find())
        
        total_synced = sum(s.get("documents_synced", 0) for s in states)
        failed_datasets = [s["dataset_id"] for s in states if s.get("status") == "failed"]
        
        # Get ES count
        try:
            es_count = self.es.count(index=self.es_index)["count"]
        except:
            es_count = 0
        
        # Get MongoDB count
        mongo_count = self.silver.count_documents({})
        
        return {
            "datasets_tracked": len(states),
            "total_documents_synced": total_synced,
            "elasticsearch_documents": es_count,
            "mongodb_documents": mongo_count,
            "sync_gap": mongo_count - es_count,
            "failed_datasets": failed_datasets,
            "last_sync": max(
                (s.get("last_synced_at") for s in states if s.get("last_synced_at")),
                default=None
            ),
        }
    
    
    def _delete_es_documents(self, dataset_id: str):
        """Delete all ES documents for a dataset."""
        try:
            self.es.delete_by_query(
                index=self.es_index,
                body={"query": {"term": {"dataset_id": dataset_id}}},
                conflicts="proceed",
            )
            self.es.indices.refresh(index=self.es_index)
        except Exception as e:
            logger.warning(f"Could not delete ES documents for {dataset_id}: {e}")
    
    def _recreate_es_index(self):
        """Recreate Elasticsearch index."""
        if self.es.indices.exists(index=self.es_index):
            self.es.indices.delete(index=self.es_index)
            logger.info(f"Deleted index: {self.es_index}")
        
        # Note: Index will be recreated with mapping by GoldLayer
        logger.info(f"Index {self.es_index} will be recreated on first write")
    
    

# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def quick_sync(datasets: List[str] = None, categories: List[str] = None, **kwargs) -> Dict[str, SyncResult]:
    """Quick incremental sync."""
    return SyncManager(**kwargs).incremental_sync(datasets=datasets, categories=categories)


def full_resync(**kwargs) -> Dict[str, SyncResult]:
    """Full resync of all data."""
    return SyncManager(**kwargs).full_resync()


def get_sync_status(**kwargs) -> Dict[str, Any]:
    """Get current sync status."""
    return SyncManager(**kwargs).get_sync_status()


__all__ = [ "SyncManager", "SyncResult", "SyncStatus", 
            "quick_sync", "full_resync", "get_sync_status" 
        ]
