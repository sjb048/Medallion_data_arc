# elasticsearch/indexer.py
# Elasticsearch indexer for Toronto Open Data

import os
import json
import logging
from typing import Dict, List, Optional, Generator

from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk

from .config import DEFAULT_ES_CONFIG
from .mapping import UNIFIED_MAPPING
from .normalizer import prepare_document

logger = logging.getLogger(__name__)


class UnifiedIndexer:
    """
    Unified Elasticsearch indexer for all Toronto Open Data types.
    
    Features:
    - Single index handles all data types (health, housing, transportation, etc.)
    - Filter by primary_issue to query specific data types
    - Auto-normalizes field names
    - Builds searchable_text for full-text search
    - Handles geospatial data (geo_shape, geo_point)
    - Supports bulk indexing
    
    Usage:
        indexer = UnifiedIndexer()
        indexer.create_index()
        indexer.index_directory("./data/json")
    """
    
    def __init__(
        self,
        es_host: str = None,
        es_user: str = None,
        es_password: str = None,
        index_name: str = None,
        timeout: int = None
    ):
        """
        Initialize the indexer.
        
        Args:
            es_host: Elasticsearch host URL (default: http://localhost:9200)
            es_user: Username for authentication (optional)
            es_password: Password for authentication (optional)
            index_name: Index name (default: toronto-opendata)
            timeout: Request timeout in seconds (default: 60)
        """
        # Apply defaults
        es_host = es_host or DEFAULT_ES_CONFIG["host"]
        index_name = index_name or DEFAULT_ES_CONFIG["index_name"]
        timeout = timeout or DEFAULT_ES_CONFIG["timeout"]
        
        # Build connection kwargs
        conn_kwargs = {
            "request_timeout": timeout,
            "retry_on_timeout": True,
            "max_retries": 3
        }
        
        if es_user and es_password:
            conn_kwargs["basic_auth"] = (es_user, es_password)
            conn_kwargs["verify_certs"] = False
        
        # Connect to Elasticsearch
        self.es = Elasticsearch(es_host, **conn_kwargs)
        self.index_name = index_name
        self.es_host = es_host
        
        # Verify connection
        if not self.es.ping():
            raise ConnectionError(f"Cannot connect to Elasticsearch at {es_host}")
        
        logger.info(f"Connected to Elasticsearch at {es_host}")
        print(f"✅ Connected to Elasticsearch at {es_host}")
    
    # =========================================================================
    # INDEX MANAGEMENT
    # =========================================================================
    
    def create_index(self, delete_existing: bool = False) -> bool:
        """
        Create the index with unified mapping.
        
        Args:
            delete_existing: If True, delete existing index first
            
        Returns:
            True if successful
        """
        try:
            if self.es.indices.exists(index=self.index_name):
                if delete_existing:
                    self.es.indices.delete(index=self.index_name)
                    print(f"   🗑️ Deleted existing index '{self.index_name}'")
                else:
                    print(f"   ℹ️ Index '{self.index_name}' already exists")
                    return True
            
            self.es.indices.create(index=self.index_name, body=UNIFIED_MAPPING)
            print(f"   ✅ Created index '{self.index_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            print(f"   ❌ Failed to create index: {e}")
            return False
    
    def delete_index(self) -> bool:
        """Delete the index."""
        try:
            if self.es.indices.exists(index=self.index_name):
                self.es.indices.delete(index=self.index_name)
                print(f"   🗑️ Deleted index '{self.index_name}'")
                return True
            else:
                print(f"   ℹ️ Index '{self.index_name}' does not exist")
                return True
        except Exception as e:
            logger.error(f"Failed to delete index: {e}")
            print(f"   ❌ Failed to delete index: {e}")
            return False
    
    def refresh_index(self):
        """Refresh the index to make recent changes searchable."""
        try:
            self.es.indices.refresh(index=self.index_name)
        except Exception as e:
            logger.warning(f"Failed to refresh index: {e}")
    
    # =========================================================================
    # INDEXING METHODS
    # =========================================================================
    
    def _generate_bulk_actions(
        self,
        records: List[Dict],
        metadata: Dict
    ) -> Generator[Dict, None, None]:
        """Generate bulk actions for streaming_bulk."""
        dataset_id = metadata.get("dataset_id", "unknown")
        
        for i, record in enumerate(records):
            doc = prepare_document(record, metadata)
            doc["doc_id"] = f"{dataset_id}_{i}"
            
            yield {
                "_index": self.index_name,
                "_id": doc["_unique_id"],
                "_source": doc
            }
    
    def index_dataset(
        self,
        enriched_data: Dict,
        batch_size: int = 500
    ) -> Dict:
        """
        Index an enriched dataset.
        
        Args:
            enriched_data: Dict with '_metadata' and 'records' keys
                          (output from HousingDataDownloader)
            batch_size: Number of documents per bulk request
            
        Returns:
            Dict with indexing statistics
        """
        metadata = enriched_data.get("_metadata", {})
        records = enriched_data.get("records", [])
        
        if not records:
            logger.warning("No records to index")
            return {"indexed": 0, "failed": 0}
        
        dataset_id = metadata.get("dataset_id", "unknown")
        primary_issue = metadata.get("primary_issue", "uncategorized")
        
        print(f"\n📤 Indexing: {dataset_id}")
        print(f"   Records: {len(records)} | Issue: {primary_issue}")
        
        # Ensure index exists
        self.create_index()
        
        # Bulk index
        try:
            success = 0
            failed = 0
            errors = []
            
            for ok, result in streaming_bulk(
                self.es,
                self._generate_bulk_actions(records, metadata),
                chunk_size=batch_size,
                raise_on_error=False,
                raise_on_exception=False
            ):
                if ok:
                    success += 1
                else:
                    failed += 1
                    if len(errors) < 5:  # Keep first 5 errors
                        errors.append(result)
            
            # Log results
            print(f"   ✅ Indexed: {success}")
            if failed > 0:
                print(f"   ❌ Failed: {failed}")
                for err in errors[:3]:
                    logger.error(f"Index error: {err}")
            
            return {
                "indexed": success,
                "failed": failed,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")
            print(f"   ❌ Bulk indexing failed: {e}")
            return {
                "indexed": 0,
                "failed": len(records),
                "error": str(e)
            }
    
    def index_json_file(self, filepath: str, batch_size: int = 500) -> Dict:
        """
        Index a JSON file.
        
        Args:
            filepath: Path to JSON file (output from save_enriched_json)
            batch_size: Number of documents per bulk request
            
        Returns:
            Dict with indexing statistics
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                enriched_data = json.load(f)
            return self.index_dataset(enriched_data, batch_size)
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            print(f"   ❌ Failed to load {filepath}: {e}")
            return {"indexed": 0, "failed": 0, "error": str(e)}
    
    def index_directory(self, json_dir: str, batch_size: int = 500) -> Dict:
        """
        Index all JSON files in a directory.
        
        Args:
            json_dir: Directory containing JSON files
            batch_size: Number of documents per bulk request
            
        Returns:
            Dict with total indexing statistics
        """
        results = {
            "total_indexed": 0,
            "total_failed": 0,
            "files_processed": 0,
            "files_failed": []
        }
        
        if not os.path.exists(json_dir):
            print(f"❌ Directory not found: {json_dir}")
            return results
        
        # Find all JSON files
        json_files = [f for f in os.listdir(json_dir) if f.endswith('.json')]
        print(f"\n📁 Found {len(json_files)} JSON files in {json_dir}")
        
        for filename in json_files:
            filepath = os.path.join(json_dir, filename)
            result = self.index_json_file(filepath, batch_size)
            
            results["total_indexed"] += result.get("indexed", 0)
            results["total_failed"] += result.get("failed", 0)
            results["files_processed"] += 1
            
            if result.get("error"):
                results["files_failed"].append(filename)
        
        # Summary
        print(f"\n{'='*50}")
        print(f"📊 INDEXING COMPLETE")
        print(f"{'='*50}")
        print(f"   Files processed: {results['files_processed']}")
        print(f"   Total indexed:   {results['total_indexed']}")
        print(f"   Total failed:    {results['total_failed']}")
        
        if results["files_failed"]:
            print(f"   Failed files:    {results['files_failed']}")
        
        return results
    
    # =========================================================================
    # DOCUMENT OPERATIONS
    # =========================================================================
    
    def index_document(self, doc: Dict, doc_id: str = None) -> bool:
        """Index a single document."""
        try:
            self.es.index(
                index=self.index_name,
                id=doc_id,
                document=doc
            )
            return True
        except Exception as e:
            logger.error(f"Failed to index document: {e}")
            return False
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a single document by ID."""
        try:
            self.es.delete(index=self.index_name, id=doc_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False
    
    def delete_by_dataset(self, dataset_id: str) -> int:
        """
        Delete all documents for a specific dataset.
        
        Returns:
            Number of documents deleted
        """
        try:
            result = self.es.delete_by_query(
                index=self.index_name,
                body={
                    "query": {
                        "term": {"dataset_id": dataset_id}
                    }
                }
            )
            deleted = result.get("deleted", 0)
            print(f"   🗑️ Deleted {deleted} documents for dataset '{dataset_id}'")
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete by dataset: {e}")
            return 0
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self) -> Dict:
        """
        Get index statistics.
        
        Returns:
            Dict with total count and counts by primary_issue
        """
        try:
            # Get total count
            total = self.es.count(index=self.index_name)["count"]
            
            # Get counts by primary_issue
            body = {
                "size": 0,
                "aggs": {
                    "by_issue": {
                        "terms": {
                            "field": "primary_issue",
                            "size": 20
                        }
                    },
                    "by_dataset": {
                        "terms": {
                            "field": "dataset_id",
                            "size": 50
                        }
                    }
                }
            }
            
            response = self.es.search(index=self.index_name, body=body)
            
            by_issue = {
                bucket["key"]: bucket["doc_count"]
                for bucket in response["aggregations"]["by_issue"]["buckets"]
            }
            
            by_dataset = {
                bucket["key"]: bucket["doc_count"]
                for bucket in response["aggregations"]["by_dataset"]["buckets"]
            }
            
            return {
                "total": total,
                "by_issue": by_issue,
                "by_dataset": by_dataset
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"total": 0, "by_issue": {}, "by_dataset": {}}
    
    def get_mapping(self) -> Dict:
        """Get the current index mapping."""
        try:
            return self.es.indices.get_mapping(index=self.index_name)
        except Exception as e:
            logger.error(f"Failed to get mapping: {e}")
            return {}