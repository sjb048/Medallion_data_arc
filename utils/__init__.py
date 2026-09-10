"""
Utils package for votes downloader
"""

from .file_utils import (
    get_filename_from_url, 
    get_base_path,
    ensure_directory_exists, 
    file_exists_prompt
)

from .db_connect import (
    connect_to_db,
    # insert_data_into_mongodb
)
from .config_db import (
    get_mongodb_config,
    get_mongodb_uri,
    get_collections_to_use,
    # get_mongodb_connector_config,
    get_pipeline_config,
    get_elasticsearch_config,
    get_transformer_config,
    getxml_config,
    get_feed_urls
    # test_url
)

from .extract_feed_methods import(
    find_tags_type,
    find_tags_url,
    duplicate_feeds,
    is_feed_url
)
__all__ = [
    'get_filename_from_url',
    'get_base_path', 
    'ensure_directory_exists', 
    'file_exists_prompt',

    # Multi-step exports
    'detect_multi_step_exports',

    # Link finding
    'find_export_links_by_text',
    'find_export_links_by_extension',
    'find_all_export_links',
    

    #db connection
    'connect_to_db',

    #Extract_feed methods
    'find_tags_type',
    'find_tags_url',
    'duplicate_feeds',
    'is_feed_url',
    #config
    'get_mongodb_config',
    'get_mongodb_uri',
    'get_collections_to_use',
    # 'get_mongodb_connector_config',
    'get_pipeline_config',
    'get_elasticsearch_config',
    'get_transformer_config',
    'getxml_config',
    'get_feed_urls',
    # 'test_url'

]