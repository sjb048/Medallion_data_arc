from .bronze_layer import (
    BronzeLayer,
    get_bronze
)
from .silver_layer import (
    SilverLayer,
    get_silver,
)
from .gold_layer import (
    GoldLayer,
    get_gold
)

from .deduplication import (
    normalize_resource_name,
    names_match,
    extract_base_name_for_grouping,
    get_resource_signature,
    are_format_duplicates, 
    deduplicate_resources,
    categorize_resources,
    group_by_name,
    group_by_base_name,
    find_duplicates,
    get_duplicate_summary,
    get_yearly_resources_summary,
)

from .file_format import (
    get_resource_priority,
    get_format_priority,
    is_supported_format,
    FORMAT_PRIORITY,
    SUPPORTED_FORMATS,
    GEO_KEYWORDS,
    detect_format,
    detect_format_from_url,
    get_file_extension,
    sort_by_priority,
    filter_supported,
    get_best_resource

)
from .mapping import (
    FIELD_MAP,
    BOOLEAN_FIELDS,
    NULL_VALUES,
    parse_boolean,
    add_field_mapping,
    get_all_mappings
)
from .metadata import(
    get_issue_mapping,
    get_secondary_issues,
    infer_primary_issue,
    infer_subcategory,
    get_issue_keywords,
    DATA_TYPE_PATTERNS,
    infer_data_type,
    build_metadata

)
from .searchable_text_builder import(
    SEARCHABLE_FIELDS,
    build_searchable_text,
    get_fields_for_issue
)
from .taxonomy import (
    ISSUE_TAXONOMY,
    DATASET_ISSUE_MAP
)
from .filepath import(
    get_raw_filepath,
    get_json_filepath,
    get_logs_filepath,
    ensure_directories,
    normalize_record,
    clean_filename
)
from .web import (
   
    fetch_json_from_url,
    fetch_datastore_records,
    fetch_package_metadata
)


__all__ = [
    #layer 
    'BronzeLayer',
    'get_bronze',
    'SilverLayer',
    'get_silver', 
    
    # Gold
    "GoldLayer", "get_gold",

    #deduplication starts
    'normalize_resource_name',
    'names_match',
    'extract_base_name_for_grouping',
    'get_resource_signature',
    'are_format_duplicates',
    
    # Deduplication
    'deduplicate_resources',
    
    # Categorization
    'categorize_resources',
    'group_by_name',
    'group_by_base_name',
    
    # Analysis
    'find_duplicates',
    'get_duplicate_summary',
    'get_yearly_resources_summary',

    #deduplication ends

    'FORMAT_PRIORITY',
    'SUPPORTED_FORMATS',
    'GEO_KEYWORDS',
    
    # Priority functions
    'get_format_priority',
    'get_resource_priority',
    'is_supported_format',
    
    # Detection helpers
    'detect_format',
    'detect_format_from_url',
    'get_file_extension',
    
    
    # Sorting & filtering
    'sort_by_priority',
    'filter_supported',
    'get_best_resource',

    # Mapping file 
    'get_issue_mapping',
    'FIELD_MAP',
    'BOOLEAN_FIELDS',
    'NULL_VALUES',
    'parse_boolean',
    'add_field_mapping',
    'get_all_mappings',

    #metadata files
     'infer_primary_issue',
    'infer_subcategory',
    'get_secondary_issues',
    'get_issue_keywords',
    # Data type
    'DATA_TYPE_PATTERNS',
    'infer_data_type',
    # Builder
    'build_metadata',

     #searchable_text_field
    'SEARCHABLE_FIELDS',
    'build_searchable_text',
    'get_fields_for_issue',

    #taxonomy files
    'ISSUE_TAXONOMY',
    'DATASET_ISSUE_MAP',

    #utils Files
    'get_raw_filepath',
    'get_json_filepath',
    'get_logs_filepath',
    'ensure_directories',
    'normalize_record',
    # Filename helpers
    'clean_filename'

     #web files
    'fetch_json_from_url',
    'fetch_datastore_records',
    'fetch_package_metadata'
]