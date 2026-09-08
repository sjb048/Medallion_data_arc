# elasticsearch/searcher.py
# Elasticsearch search functionality for Toronto Open Data

import logging
from typing import Dict, List, Optional, Any

from elasticsearch import Elasticsearch

from .config import DEFAULT_ES_CONFIG

logger = logging.getLogger(__name__)


class UnifiedSearcher:
    """
    Search functionality for Toronto Open Data.
    
    Provides convenience methods for searching by data type:
    - search_health() - DineSafe, BodySafe, beaches, etc.
    - search_housing() - Condos, apartments, rentals
    - search_transportation() - Traffic, TTC, cycling
    - search_safety() - Crime, incidents
    - search_environment() - Parks, trees, water
    - search_business() - Licenses, permits
    
    Usage:
        searcher = UnifiedSearcher()
        
        # Search all data
        results = searcher.search(query="restaurant")
        
        # Search specific type
        results = searcher.search_health(query="fail")
        
        # Search with filters
        results = searcher.search(
            primary_issue="health",
            filters={"insStatus": "Fail"},
            geo={"lat": 43.65, "lon": -79.38, "distance": "2km"}
        )
    """
    
    def __init__(
        self,
        es_host: str = None,
        es_user: str = None,
        es_password: str = None,
        index_name: str = None
    ):
        """Initialize the searcher."""
        es_host = es_host or DEFAULT_ES_CONFIG["host"]
        index_name = index_name or DEFAULT_ES_CONFIG["index_name"]
        
        conn_kwargs = {"request_timeout": 30}
        if es_user and es_password:
            conn_kwargs["basic_auth"] = (es_user, es_password)
        
        self.es = Elasticsearch(es_host, **conn_kwargs)
        self.index_name = index_name
        
        if not self.es.ping():
            raise ConnectionError(f"Cannot connect to Elasticsearch at {es_host}")
    
    # =========================================================================
    # MAIN SEARCH METHOD
    # =========================================================================
    
    def search(
        self,
        query: str = None,
        primary_issue: str = None,
        filters: Dict[str, Any] = None,
        geo: Dict = None,
        date_range: Dict = None,
        sort: List[Dict] = None,
        size: int = 10,
        from_: int = 0,
        fields: List[str] = None,
        highlight: bool = False
    ) -> Dict:
        """
        Search indexed data.
        
        Args:
            query: Full-text search query (searches searchable_text and other fields)
            primary_issue: Filter by issue type (health, housing, transportation, etc.)
            filters: Dict of field:value filters (exact match)
            geo: Geo distance filter {"lat": x, "lon": y, "distance": "5km"}
            date_range: Date range filter {"field": "insDate", "gte": "2024-01-01", "lte": "2024-12-31"}
            sort: Sort specification [{"field": "desc"}]
            size: Number of results (default: 10)
            from_: Offset for pagination (default: 0)
            fields: Specific fields to return (default: all)
            highlight: Whether to highlight matches (default: False)
            
        Returns:
            Dict with 'hits', 'total', and optionally 'aggregations'
        """
        must = []
        filter_clauses = []
        
        # Full-text search
        if query:
            must.append({
                "multi_match": {
                    "query": query,
                    "fields": [
                        "searchable_text^3",
                        "estName^2",
                        "business_name^2",
                        "address^2",
                        "addrFull^2",
                        "park_name^2",
                        "intersection^2",
                        "*"
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            })
        
        # Filter by primary_issue
        if primary_issue:
            filter_clauses.append({
                "term": {"primary_issue": primary_issue}
            })
        
        # Additional field filters
        if filters:
            for field, value in filters.items():
                if isinstance(value, list):
                    filter_clauses.append({"terms": {field: value}})
                else:
                    filter_clauses.append({"term": {field: value}})
        
        # Geo distance filter
        if geo:
            filter_clauses.append({
                "geo_distance": {
                    "distance": geo.get("distance", "5km"),
                    "location": {
                        "lat": geo["lat"],
                        "lon": geo["lon"]
                    }
                }
            })
        
        # Date range filter
        if date_range:
            field = date_range.get("field", "date")
            range_query = {field: {}}
            if "gte" in date_range:
                range_query[field]["gte"] = date_range["gte"]
            if "lte" in date_range:
                range_query[field]["lte"] = date_range["lte"]
            filter_clauses.append({"range": range_query})
        
        # Build query body
        body = {
            "query": {
                "bool": {
                    "must": must if must else [{"match_all": {}}],
                    "filter": filter_clauses
                }
            },
            "size": size,
            "from": from_
        }
        
        # Add sort
        if sort:
            body["sort"] = sort
        else:
            body["sort"] = [{"@timestamp": "desc"}]
        
        # Add source filtering
        if fields:
            body["_source"] = fields
        
        # Add highlighting
        if highlight:
            body["highlight"] = {
                "fields": {
                    "searchable_text": {},
                    "estName": {},
                    "address": {},
                    "observation": {},
                    "defDesc": {}
                }
            }
        
        try:
            response = self.es.search(index=self.index_name, body=body)
            
            return {
                "hits": [hit["_source"] for hit in response["hits"]["hits"]],
                "total": response["hits"]["total"]["value"],
                "highlights": [
                    hit.get("highlight", {}) 
                    for hit in response["hits"]["hits"]
                ] if highlight else None
            }
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {"hits": [], "total": 0, "error": str(e)}
    
    # =========================================================================
    # CONVENIENCE SEARCH METHODS BY DATA TYPE
    # =========================================================================
    
    def search_health(self, query: str = None, **kwargs) -> Dict:
        """
        Search health data (DineSafe, BodySafe, beaches, etc.)
        
        Examples:
            search_health(query="restaurant fail")
            search_health(filters={"insStatus": "Fail"})
            search_health(query="beach", filters={"beachAdvisory": "Yes"})
        """
        return self.search(query=query, primary_issue="health", **kwargs)
    
    def search_housing(self, query: str = None, **kwargs) -> Dict:
        """
        Search housing data (condos, apartments, rentals, etc.)
        
        Examples:
            search_housing(query="condo downtown")
            search_housing(filters={"building_type": "Condominium"})
        """
        return self.search(query=query, primary_issue="housing", **kwargs)
    
    def search_transportation(self, query: str = None, **kwargs) -> Dict:
        """
        Search transportation data (traffic, TTC, cycling, etc.)
        
        Examples:
            search_transportation(query="King Street")
            search_transportation(filters={"direction": "EB"})
        """
        return self.search(query=query, primary_issue="transportation", **kwargs)
    
    def search_safety(self, query: str = None, **kwargs) -> Dict:
        """
        Search public safety data (crime, incidents, etc.)
        
        Examples:
            search_safety(query="theft")
            search_safety(filters={"division": "D14"})
        """
        return self.search(query=query, primary_issue="public_safety", **kwargs)
    
    def search_environment(self, query: str = None, **kwargs) -> Dict:
        """
        Search environment data (parks, trees, water, etc.)
        
        Examples:
            search_environment(query="High Park")
            search_environment(filters={"facility_type": "Playground"})
        """
        return self.search(query=query, primary_issue="environment", **kwargs)
    
    def search_business(self, query: str = None, **kwargs) -> Dict:
        """
        Search business/economy data (licenses, permits, etc.)
        
        Examples:
            search_business(query="restaurant")
            search_business(filters={"license_status": "Active"})
        """
        return self.search(query=query, primary_issue="business_and_economy", **kwargs)
    
    def search_permits(self, query: str = None, **kwargs) -> Dict:
        """
        Search permit data.
        
        Examples:
            search_permits(filters={"permit_type": "Building"})
        """
        return self.search(query=query, primary_issue="permits", **kwargs)
    
    # =========================================================================
    # SPECIALIZED SEARCH METHODS
    # =========================================================================
    
    def search_nearby(
        self,
        lat: float,
        lon: float,
        distance: str = "1km",
        primary_issue: str = None,
        size: int = 20
    ) -> Dict:
        """
        Search for records near a location.
        
        Args:
            lat: Latitude
            lon: Longitude
            distance: Search radius (e.g., "1km", "500m", "5mi")
            primary_issue: Optional filter by issue type
            size: Number of results
            
        Returns:
            Dict with hits sorted by distance
        """
        return self.search(
            primary_issue=primary_issue,
            geo={"lat": lat, "lon": lon, "distance": distance},
            sort=[{
                "_geo_distance": {
                    "location": {"lat": lat, "lon": lon},
                    "order": "asc",
                    "unit": "km"
                }
            }],
            size=size
        )
    
    def search_recent(
        self,
        days: int = 30,
        primary_issue: str = None,
        date_field: str = "@timestamp",
        size: int = 20
    ) -> Dict:
        """
        Search for recently indexed records.
        
        Args:
            days: Number of days to look back
            primary_issue: Optional filter by issue type
            date_field: Field to use for date filtering
            size: Number of results
        """
        return self.search(
            primary_issue=primary_issue,
            date_range={
                "field": date_field,
                "gte": f"now-{days}d"
            },
            sort=[{date_field: "desc"}],
            size=size
        )
    
    def search_by_ward(
        self,
        ward: str,
        primary_issue: str = None,
        query: str = None,
        size: int = 50
    ) -> Dict:
        """
        Search for records in a specific ward.
        
        Args:
            ward: Ward number or name
            primary_issue: Optional filter by issue type
            query: Optional text query
            size: Number of results
        """
        return self.search(
            query=query,
            primary_issue=primary_issue,
            filters={"ward": ward},
            size=size
        )
    
    def search_by_neighbourhood(
        self,
        neighbourhood: str,
        primary_issue: str = None,
        query: str = None,
        size: int = 50
    ) -> Dict:
        """
        Search for records in a specific neighbourhood.
        
        Args:
            neighbourhood: Neighbourhood name
            primary_issue: Optional filter by issue type
            query: Optional text query
            size: Number of results
        """
        # Use match query for neighbourhood since it's analyzed
        filters = {}
        must = []
        
        if neighbourhood:
            must.append({
                "match": {
                    "neighbourhood": neighbourhood
                }
            })
        
        return self.search(
            query=query,
            primary_issue=primary_issue,
            filters=filters,
            size=size
        )
    
    # =========================================================================
    # AGGREGATIONS
    # =========================================================================
    
    def aggregate(
        self,
        field: str,
        primary_issue: str = None,
        size: int = 20
    ) -> Dict[str, int]:
        """
        Get term aggregation for a field.
        
        Args:
            field: Field to aggregate on
            primary_issue: Optional filter by issue type
            size: Number of buckets
            
        Returns:
            Dict of term: count
        """
        body = {
            "size": 0,
            "aggs": {
                "by_field": {
                    "terms": {
                        "field": field,
                        "size": size
                    }
                }
            }
        }
        
        if primary_issue:
            body["query"] = {
                "term": {"primary_issue": primary_issue}
            }
        
        try:
            response = self.es.search(index=self.index_name, body=body)
            return {
                bucket["key"]: bucket["doc_count"]
                for bucket in response["aggregations"]["by_field"]["buckets"]
            }
        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            return {}
    
    def get_issue_counts(self) -> Dict[str, int]:
        """Get document counts by primary_issue."""
        return self.aggregate("primary_issue")
    
    def get_dataset_counts(self) -> Dict[str, int]:
        """Get document counts by dataset_id."""
        return self.aggregate("dataset_id", size=100)
    
    def get_status_counts(self, primary_issue: str = None) -> Dict[str, int]:
        """Get document counts by status."""
        return self.aggregate("status", primary_issue=primary_issue)