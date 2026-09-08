import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from bronze_layer import BronzeLayer, get_bronze
from silver_layer import SilverLayer, get_silver
from gold_layer import GoldLayer, get_gold


class MedallionLoader:
    
    def __init__(
        self,
        mongo_uri: str = "mongodb://localhost:27017",
        database: str = "policy_issues",
        es_hosts: List[str] = None,
        es_index: str = "policy_issues_toronto",
        enable_gold: bool = True
    ):
        """
        Initialize Medallion Loader.
        
        Args:
            mongo_uri: MongoDB connection string
            database: MongoDB database name
            es_hosts: Elasticsearch hosts
            es_index: Elasticsearch index name
            enable_gold: Whether to enable Gold layer (ES)
        """
        # Initialize layers
        self.bronze = BronzeLayer(mongo_uri=mongo_uri, database=database)
        self.silver = SilverLayer(mongo_uri=mongo_uri, database=database)
        
        self.enable_gold = enable_gold
        if enable_gold:
            try:
                self.gold = GoldLayer(es_hosts=es_hosts, index_name=es_index)
            except Exception as e:
                print(f"⚠️  Gold layer (Elasticsearch) not available: {e}")
                self.gold = None
                self.enable_gold = False
        else:
            self.gold = None
        
        print(f"✅ Medallion Loader initialized")
        print(f"   Bronze: {self.bronze.collection.name}")
        print(f"   Silver: {self.silver.collection.name}")
        if self.gold:
            print(f"   Gold:   {self.gold.index_name}")
    
     # =========================================================================
    # MAIN LOADING API
    # =========================================================================
    
    def load_record(
        self,
        record: Dict,
        dataset_id: str,
        metadata: Dict = None,
        source_file: str = None,
        skip_gold: bool = False
    ) -> Dict[str, bool]:
        """
        Load a single record through the entire pipeline.
        
        Args:
            record: Raw record
            dataset_id: Dataset identifier
            metadata: Additional metadata (primary_issue, etc.)
            source_file: Source file name
            skip_gold: Skip Gold layer indexing
            
        Returns:
            Dict with layer success status
        """
        result = {"bronze": False, "silver": False, "gold": False}
        metadata = metadata or {}
        
        try:
            # BRONZE: Store raw
            self.bronze.store(record, dataset_id, source_file)
            result["bronze"] = True
            
            # SILVER: Normalize and store
            self.silver.store(record, dataset_id, metadata)
            result["silver"] = True
            
            # GOLD: Index for search
            if self.enable_gold and self.gold and not skip_gold:
                normalized = self.silver.normalize_record(record)
                normalized["dataset_id"] = dataset_id
                normalized.update(metadata)
                self.gold.index(normalized, dataset_id)
                result["gold"] = True
                
        except Exception as e:
            print(f"❌ Error loading record: {e}")
        
        return result
    