# gold_layer.py
"""
GOLD LAYER - Elasticsearch Search Index

Search-optimized data with aggregations, geo queries, and fast retrieval.
Can reprocess from Silver layer when mappings change.

Elasticsearch Index: policy_issues_toronto

Usage:
    from gold_layer import GoldLayer
    
    gold = GoldLayer()
    gold.index(record, dataset_id="outbreaks")
    gold.reprocess_from_silver(silver_layer)
    gold.search("nursing home outbreak")
"""

import logging
import urllib3
from datetime import datetime
from typing import Dict, List, Any, Optional, Generator
from elasticsearch import Elasticsearch, helpers
import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent      # OpenData/common/
OPENDATA_DIR = SCRIPT_DIR.parent                  # OpenData/  (ONE level up, not two!)
sys.path.insert(0, str(OPENDATA_DIR))


from ES.es_config import (
    ES_CONFIG, DEFAULT_ES_INDEX, DEFAULT_BATCH_SIZE, UNIFIED_MAPPING, SEARCH_BOOST_FIELDS,
   
)

from ES.es_doc import prepare_es_document, get_doc_id

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
    print(username)
    es_kwargs = {
        'hosts': hosts,
        'verify_certs': config.get('verify_certs', False),
        'ssl_show_warn': config.get('ssl_show_warn', False),
        'timeout': config.get('timeout', 30),
    }
    
    if username and password:
        es_kwargs['basic_auth'] = (username, password)
    
    return Elasticsearch(**es_kwargs)


class GoldLayer:
    """
    Gold Layer: Elasticsearch search index.
    
    OPTIMIZED FOR:
    - Full-text search
    - Aggregations (facets)
    - Geo queries
    - Fast retrieval
    - Autocomplete
    """
    
    INDEX_NAME = os.getenv("ELASTICSEARCH_INDEX", "policy_issues_toronto")
    
    def __init__(
        self,
        es_config: Dict = None,
        index_name: str = None,
        mapping: Dict = None,
        domain_config: Dict = None,
        es_hosts: List[str] = None,
    ):
        """
        Initialize Gold Layer.
        
        Args:
            es_hosts: Elasticsearch hosts (default: localhost:9200)
            index_name: Index name (default: policy_issues_toronto)
            mapping: Custom index mapping
        """

        if es_config:
            self.es_config = es_config
        elif es_hosts:
            self.es_config = {**ES_CONFIG, 'hosts': es_hosts}
        else:
            self.es_config = ES_CONFIG
        # Elasticsearch with SSL settings
        self.es = create_es_client(self.es_config)
        self.index_name = index_name or DEFAULT_ES_INDEX
        self.mapping = mapping or UNIFIED_MAPPING
        self.domain_config = domain_config or {}
        
        # Ensure index exists
        self._ensure_index()
    
    def _ensure_index(self):
        """Create index if it doesn't exist."""
        if not self.es.indices.exists(index=self.index_name):
            self.es.indices.create(index=self.index_name, body=self.mapping)
            print(f"✅ Created index: {self.index_name}")
    
    # =========================================================================
    # INDEXING
    # =========================================================================
    
    def index(self,record: Dict, dataset_id: str = None) -> str:
        """ Index a single record.
        Args:
            record: Normalized record (from Silver layer)
            dataset_id: Dataset identifier (optional, taken from record)
            
        Returns:
            Document ID
        """
        doc = prepare_es_document(record, dataset_id)
        doc_id = get_doc_id(doc)
       
        
        self.es.index( index=self.index_name,id=doc_id,document=doc)
        
        return doc_id
    
    def index_batch(
        self,
        records: List[Dict], dataset_id: str = None, chunk_size: int = DEFAULT_BATCH_SIZE, refresh: bool = True,
    ) -> Dict[str, int]:
        """
        Index multiple records efficiently using bulk API.
        
        Args:
            records: List of normalized records
            dataset_id: Dataset identifier
            chunk_size: Bulk chunk size
            
        Returns:
            Stats dict
        """
        if not records:
            return {"indexed": 0, "errors": 0}
        
        def actions():
            for record in records:
                doc = prepare_es_document(record, dataset_id)
                yield {
                    "_index": self.index_name,
                    "_id": get_doc_id(doc),
                    "_source": doc,
                }
        
        success, errors = helpers.bulk(
            self.es,
            actions(),
            chunk_size=chunk_size,
            raise_on_error=False
        )
        if refresh:
            self.es.indices.refresh(index=self.index_name)

        return {
            "indexed": success,
            "errors": len(errors) if isinstance(errors, list) else errors
        }
    
    def index_from_generator(
        self,
        documents: Generator[Dict, None, None],
        dataset_id: str = None,
        chunk_size: int = DEFAULT_BATCH_SIZE,
    ) -> Dict[str, int]:
        """Index from generator (memory efficient)."""
        def actions():
            for record in documents:
                doc = prepare_es_document(record, dataset_id)
                yield {
                    "_index": self.index_name,
                    "_id": get_doc_id(doc),
                    "_source": doc,
                }
        
        success, errors = 0, 0
        for ok, result in helpers.streaming_bulk(
            self.es, actions(),
            chunk_size=chunk_size,
            raise_on_error=False,
            raise_on_exception=False,
        ):
            if ok:
                success += 1
            else:
                errors += 1
        
        self.es.indices.refresh(index=self.index_name)
        return {"indexed": success, "errors": errors}
    
   # =========================================================================
    # DELETION
    # =========================================================================
    
    def delete_by_dataset(self, dataset_id: str) -> int:
        """Delete all documents for a dataset."""
        result = self.es.delete_by_query(
            index=self.index_name,
            body={"query": {"term": {"dataset_id": dataset_id}}},
            conflicts="proceed",
        )
        self.es.indices.refresh(index=self.index_name)
        return result.get("deleted", 0)
    
    def delete_by_category(self, category: str) -> int:
        """Delete all documents for a category."""
        result = self.es.delete_by_query(
            index=self.index_name,
            body={"query": {"term": {"primary_issue": category}}},
            conflicts="proceed",
        )
        self.es.indices.refresh(index=self.index_name)
        return result.get("deleted", 0)
    
    
    
    # =========================================================================
    # SEARCH
    # =========================================================================
    
    def search(
        self,
        query: str,
        filters: Dict = None,
        size: int = 100,
        from_: int = 0
    ) -> Dict:
        """
        Full-text search with optional filters.
        
        Args:
            query: Search query
            filters: Dict of field:value filters
            size: Number of results
            from_: Offset for pagination
            
        Returns:
            Search results with hits and aggregations
        """
        must = []
        filter_clauses = []
        
        # Add query
        if query:
            must.append({
                "multi_match": {
                    "query": query,
                    "fields": SEARCH_BOOST_FIELDS,
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            })
        
        # Add filters

        if filters:
            for field, value in filters.items():
                if isinstance(value, list):
                    filter_clauses.append({"terms": {field: value}})
                else:
                    filter_clauses.append({"term": {field: value}})
        
        body = {
            "query": {
                "bool": {
                    "must": must if must else [{"match_all": {}}],
                    "filter": filter_clauses
                }
            },
            "size": size,
            "from": from_,
            
        }
        
        result = self.es.search(index=self.index_name, body=body)
        
        return {
            "total": result["hits"]["total"]["value"],
            "hits": [hit["_source"] for hit in result["hits"]["hits"]]
        }
    
    def search_nearby(
        self,
        lat: float,
        lon: float,
        distance: str = "5km",
        filters: Dict = None,
        size: int = 50,
    ) -> List[Dict]:
        """Search within geographic radius."""
        filter_clauses = [{
            "geo_distance": {
                "distance": distance,
                "location": {"lat": lat, "lon": lon}
            }
        }]
        
        if filters:
            for field, value in filters.items():
                filter_clauses.append({"term": {field: value}})
        
        body = {
            "query": {"bool": {"filter": filter_clauses}},
            "sort": [{
                "_geo_distance": {
                    "location": {"lat": lat, "lon": lon},
                    "order": "asc",
                    "unit": "km"
                }
            }],
            "size": size
        }
        
        result = self.es.search(index=self.index_name, body=body)
        
        hits = []
        for hit in result["hits"]["hits"]:
            doc = hit["_source"]
            doc["_distance_km"] = hit["sort"][0] if hit.get("sort") else None
            hits.append(doc)
        
        return hits
    
    
    
    def geo_search(
        self,
        lat: float,
        lon: float,
        distance: str = "5km",
        filters: Dict = None,
        size: int = 100
    ) -> List[Dict]:
        """
        Search within geographic radius.
        
        Args:
            lat: Latitude
            lon: Longitude
            distance: Search radius (e.g., "5km", "10mi")
            filters: Additional filters
            size: Number of results
            
        Returns:
            List of nearby records sorted by distance
        """
        filter_clauses = [
            {
                "geo_distance": {
                    "distance": distance,
                    "location": {"lat": lat, "lon": lon}
                }
            }
        ]
        
        if filters:
            for field, value in filters.items():
                filter_clauses.append({"term": {field: value}})
        
        body = {
            "query": {
                "bool": {
                    "filter": filter_clauses
                }
            },
            "sort": [
                {
                    "_geo_distance": {
                        "location": {"lat": lat, "lon": lon},
                        "order": "asc",
                        "unit": "km"
                    }
                }
            ],
            "size": size
        }
        
        result = self.es.search(index=self.index_name, body=body)
        
        hits = []
        for hit in result["hits"]["hits"]:
            doc = hit["_source"]
            doc["_distance_km"] = hit["sort"][0] if hit.get("sort") else None
            hits.append(doc)
        
        return hits
    
    # =========================================================================
    # AGGREGATIONS
    # =========================================================================
    
    def get_facets(self, field: str, size: int = 50) -> List[Dict]:
        """
        Get aggregated counts for a field.
        
        Args:
            field: Field to aggregate
            size: Number of buckets
            
        Returns:
            List of {value, count} dicts
        """
        body = {
            "size": 0,
            "aggs": {"facet": {"terms": {"field": field, "size": size}}}
        }
        
        result = self.es.search(index=self.index_name, body=body)
        
        return [
            {"value": b["key"], "count": b["doc_count"]}
            for b in result["aggregations"]["facet"]["buckets"]
        ]
    
    def get_stats(self) -> Dict:
        """Get index statistics."""
        count = self.es.count(index=self.index_name)
        
        # Get unique datasets
        body = {
            "size": 0,
            "aggs": {
                "datasets": {"cardinality": {"field": "dataset_id"}},
                "categories": {"terms": {"field": "primary_issue", "size": 20}},
            }
        }
        result = self.es.search(index=self.index_name, body=body)
        
        return {
            "total_documents": count["count"],
            "unique_datasets": result["aggregations"]["datasets"]["value"],
            "by_category": {
                b["key"]: b["doc_count"]
                for b in result["aggregations"]["categories"]["buckets"]
            },
        }
    
    def get_dataset_counts(self) -> Dict[str, int]:
        """Get document counts per dataset."""
        body = {
            "size": 0,
            "aggs": {"datasets": {"terms": {"field": "dataset_id", "size": 1000}}}
        }
        result = self.es.search(index=self.index_name, body=body)
        
        return {
            b["key"]: b["doc_count"]
            for b in result["aggregations"]["datasets"]["buckets"]
        }
    
    # =========================================================================
    # INDEX MANAGEMENT
    # =========================================================================
    
    def recreate_index(self):
        """Delete and recreate index."""
        if self.es.indices.exists(index=self.index_name):
            self.es.indices.delete(index=self.index_name)
        self._ensure_index()
        logger.info(f"Recreated index: {self.index_name}")
    
    def refresh(self):
        """Refresh index."""
        self.es.indices.refresh(index=self.index_name)

    # =========================================================================

# =============================================================================
# SINGLETON INSTANCE
# =============================================================================


_instance: Optional[GoldLayer] = None

def get_gold(**kwargs) -> GoldLayer:
    """Get singleton Gold Layer instance."""
    global _gold_instance
    if _gold_instance is None:
        _gold_instance = GoldLayer(**kwargs)
    return _gold_instance
DEFAULT_INDEX_MAPPING = UNIFIED_MAPPING 

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "GoldLayer",
    "get_gold",
    "DEFAULT_INDEX_MAPPING",
]