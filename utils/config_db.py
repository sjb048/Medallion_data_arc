import os
from dotenv import load_dotenv
from pathlib import Path
from pymongo import MongoClient
import logging

logger = logging.getLogger(__name__)

# Get the directory where config_db.py is located
config_dir = Path(__file__).parent.absolute()
# Go up to project root (utils -> HOLA-dashboard)
project_root = config_dir.parent
# Get project root (parent of script folder)
PROJECT_ROOT = Path(__file__).parent.parent

# Load .env.development from project root
env_path = project_root / '.env.development'
# load_dotenv(env_path)
load_dotenv(env_path, override=False)


# Verify it loaded
if not env_path.exists():
    print(f"WARNING: .env.development not found at {env_path}")
else:
    print(f"Loaded config from {env_path}")

_config_cache = {
    'mongodb': None,
    'mongodb_uri': None,
    'elasticsearch': None,
    'transformer': None
}

def clear_config_cache():
    """Clear all cached configs (useful for testing or reloading)."""
    global _config_cache
    _config_cache = {
        'mongodb': None,
        'mongodb_uri': None,
        'elasticsearch': None,
        'transformer': None
    }
    logger.info("Config cache cleared")


def getxml_config():
   
    output_dir = PROJECT_ROOT / os.getenv('RSSFEEDS_DATA_DIR', 'data/rssfeeds')

    config = {
        'timeout' : int(os.getenv('FEED_TIMEOUT', 30)),
        # 'url' : get_feed_urls(), #url is an separted by comma
        'url' : os.getenv('RSS_URL', ''),
        'headers' : {
                'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36'
                )
            },
        'output_dir': output_dir,
        'indent': 2    
    }

    return  config

def get_feed_urls():
    """Get list of feed URLs from environment or default."""
    urls_str = os.getenv('RSS_URL', '')
   
    if not urls_str:
        print("No RSS_URL configured in .env")
        return []
    
    urls = [url.strip() for url in urls_str.split(',') if url.strip()]

    # Default feeds if none configured
    return urls

# ------------------------------
# MongoDB Config
# ------------------------------

def get_mongodb_config():
    """Get configuration from environment variables with defaults."""
    global _config_cache
    if _config_cache['mongodb'] is not None:
        return _config_cache['mongodb']
    # Get json_dir from environment
    json_dir = os.getenv('JSON_DATA_DIR', 'data/json')
    
    # If it's a relative path, make it absolute relative to project root
    if not os.path.isabs(json_dir):
        json_dir = str(project_root / json_dir)
 
    collection_env = os.getenv("MONGODB_COLLECTION")
    collection = collection_env if collection_env else None  # Empty string becomes None
 
    config = {
        # Component-based config (fallback if URI not provided)
        'mongodb_user': os.getenv('MONGODB_USER'),
        'mongodb_password': os.getenv('MONGODB_PASSWORD'),
        'mongodb_host': os.getenv('MONGODB_HOST', 'localhost'),
        'mongodb_port': int(os.getenv('MONGODB_PORT', 32312)),
        'mongodb_authdb': os.getenv('MONGODB_AUTHDB', 'your auth_db_name'),
        'database': os.getenv('MONGODB_DASHBOARD_DATABASE', 'your database_name'),
        'json_dir': json_dir
        # "collection": collection
    }
    # Debug output
    
    # logger.info(f"MongoDB config loaConnected to MongoDBded: {config['mongodb_host']}:{config['mongodb_port']}/{config['database']}")
    
    _config_cache['mongodb'] = config
    return config


def get_mongodb_uri():
    """Build MongoDB URI from config."""

    global _config_cache
    
    if _config_cache['mongodb_uri'] is not None:
        return _config_cache['mongodb_uri']
    
    config = get_mongodb_config()
    
    if config["mongodb_user"] and config["mongodb_password"]:
        uri = (
            f"mongodb://{config['mongodb_user']}:{config['mongodb_password']}"
            f"@{config['mongodb_host']}:{config['mongodb_port']}"
            f"/?authSource={config['mongodb_authdb']}"
        )
    else:
        uri = f"mongodb://{config['mongodb_host']}:{config['mongodb_port']}/"
    
    _config_cache['mongodb_uri'] = uri
    return uri

# ------------------------------
# Collections
# ------------------------------

def get_collection_from_env():
    """Get collection from environment - NOT cached, always fresh."""
    collection = os.getenv("MONGODB_COLLECTION", "").strip()
    return collection if collection else None

def get_all_collections(database_name: str):
    """Return a list of all collections for a given MongoDB database."""
    client = MongoClient(get_mongodb_uri())
    try:
        db = client[database_name]
        collections = db.list_collection_names()
        collections = [c for c in collections if not c.startswith("system.")]
        return collections
    finally:
        client.close()

def get_collections_to_use(database_name: str = None):
  
    config = get_mongodb_config()
    db_name = database_name or config['database']
    # Always check env var fresh (not cached)
    collection = get_collection_from_env()

    if collection:
        # Specific collection specified in env
        logger.info(f"Using specified collection: {collection}")
        # return [config['collection']]
        return [collection]
    else:
       
        # No collection specified - fetch all from database
        # logger.info(f"No MONGODB_COLLECTION specified, fetching all collections from '{db_name}'...")
        all_collections = get_all_collections(db_name)
        # logger.info(f"Found {len(all_collections)} collections: {all_collections}")
        return all_collections


# ------------------------------
# Elasticsearch Config
# ------------------------------

def get_elasticsearch_config(index=None):
    """Get Elasticsearch configuration."""
    hosts = os.getenv('ELASTICSEARCH_HOSTS', 'https://***.***.***.***:****')
    
    if ',' in hosts:
        hosts = [h.strip() for h in hosts.split(',')]
    else:
        hosts = [hosts]
    
    return {
        'hosts': hosts,
        'index': index or os.getenv('ELASTICSEARCH_INDEX'),
        'username': os.getenv('ELASTICSEARCH_USERNAME'),
        'password': os.getenv('ELASTICSEARCH_PASSWORD')
    }


# ------------------------------
# Transformer Config
# ------------------------------

def get_transformer_config():
    """Get transformer configuration from environment variables with defaults."""
    return {
        'skip_null_fields': os.getenv('TRANSFORMER_SKIP_NULLS', 'true').lower() == 'true',
        'add_metadata': os.getenv('TRANSFORMER_ADD_METADATA', 'true').lower() == 'true'
    }


# ------------------------------
# Pipeline Config
# ------------------------------
def get_pipeline_config(collection=None):
    """Get complete pipeline configuration."""
    cfg = get_mongodb_config()
    mongodb_uri = get_mongodb_uri()
    es_config = get_elasticsearch_config()


    collections = [collection] if collection else get_collections_to_use(cfg['database'])
    logger.info(f"Collections for database '{cfg['database']}': {collections}")
    # for collection in collections:
    #     db[collection]
    base_config =  {
        'mongodb': {
            'uri': mongodb_uri,
            'database': cfg['database'],
            'collection': collections 
        },
        'elasticsearch': es_config,
        'transformer': get_transformer_config(),
        'chunk_size': int(os.getenv('CHUNK_SIZE', 100)),
        'limit': int(os.getenv('LIMIT', 0)) or None,  # 0 means no limit
        'mappings': []
        
    }
    # If collection is specified, return single collection config (backward compatible)
    if collection or os.getenv('MONGODB_COLLECTION'):
        return base_config
    
     # Get manual mappings first
    manual_mappings = parse_manual_mappings(os.getenv('PIPELINE_MAPPINGS', ''))
    
    # Get auto-discovered mappings
    auto_databases = os.getenv('AUTO_DATABASES', '')
    auto_mappings = []

    if auto_databases:
        db_prefixes = parse_db_prefixes(os.getenv('DB_INDEX_PREFIXES', ''))
        use_db_name = os.getenv('USE_DB_NAME_AS_PREFIX', 'false').lower() == 'true'
        # exclude = [c.strip() for c in os.getenv('EXCLUDE_COLLECTIONS', '').split(',') if c.strip()]
        
        auto_mappings = discover_collections(
            mongodb_uri,
            auto_databases.split(','),
            db_prefixes,
            use_db_name
            # exclude
        )
   
    manual_keys = set(f"{m['database']}.{m['collection']}" for m in manual_mappings)
    auto_filtered = [m for m in auto_mappings if f"{m['database']}.{m['collection']}" not in manual_keys]
    
    base_config['mappings'] = manual_mappings + auto_filtered
    
    if manual_mappings:
        logger.info(f"Loaded {len(manual_mappings)} manual mappings")
    if auto_filtered:
        logger.info(f"Auto-discovered {len(auto_filtered)} additional mappings")
    return base_config

def parse_manual_mappings(mappings_str):
    """
    Parse manual PIPELINE_MAPPINGS
    Format: database.collection:es_index,database.collection:es_index
    Example: parliament_data.bills:parliament-bills,rss_feeds.canada:rss-canada
    """
    mappings = []
    if not mappings_str:
        return mappings
    
    for mapping in mappings_str.split(','):
        mapping = mapping.strip()
        if ':' in mapping and '.' in mapping:
            source, target_index = mapping.split(':')
            database, collection = source.split('.')
            mappings.append({
                'database': database.strip(),
                'collection': collection.strip(),
                'es_index': target_index.strip()
            })
    
    return mappings

def parse_db_prefixes(prefix_str):
    """
    Parse database-specific prefixes
    Format: database1:prefix1,database2:prefix2
    Example: parliament_data:parliament,rss_feeds:rss
    """
    prefixes = {}
    if prefix_str:
        for item in prefix_str.split(','):
            if ':' in item:
                db, prefix = item.strip().split(':')
                prefixes[db.strip()] = prefix.strip()
    return prefixes

def discover_collections(mongo_uri, databases, db_prefixes=None, use_db_name=False):
    """
    Auto-discover collections from MongoDB databases with flexible prefix options
    
    Args:
        mongo_uri: MongoDB connection URI
        databases: List of database names to discover
        db_prefixes: Dict mapping database names to custom prefixes
        use_db_name: If True, use database name as prefix automatically
    """
    if db_prefixes is None:
        db_prefixes = {}
    
    mappings = []
    client = MongoClient(mongo_uri)
    
    for db_name in databases:
        db_name = db_name.strip()
        
        # Determine prefix for this database
        if db_name in db_prefixes:
            prefix = db_prefixes[db_name]
        elif use_db_name:
            prefix = db_name.replace('_', '-')
        else:
            prefix = ''
        
        try:
            db = client[db_name]
            collections = db.list_collection_names()
            discovered_count = 0
            logger.info(f"Discovered {len(collections)} collections in {db_name} (prefix: '{prefix}')")
            
            for collection in collections:
                # Skip system collections
                if collection.startswith('system.'):
                    continue
                
                # Create ES index name
                collection_normalized = collection.replace('_', '-')
                
                if prefix:
                    es_index = f"{prefix}-{collection_normalized}"
                else:
                    es_index = f"{db_name.replace('_', '-')}-{collection_normalized}"
                
                mappings.append({
                    'database': db_name,
                    'collection': collection,
                    'es_index': es_index
                })
                discovered_count += 1
                logger.info(f"Discovered {discovered_count} collections from {db_name} (prefix: '{prefix or 'none'}')")
             
        except Exception as e:
            logger.error(f"Error discovering collections in {db_name}: {e}")
    
    client.close()
    return mappings