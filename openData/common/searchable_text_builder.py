# searchable_text_builder.py
"""
Shared module for building searchable_text from document fields.
Used by both sync_mongo_to_es.py and searchable_text.py (fixer).
"""

# Fields to combine into searchable_text, by primary_issue
from typing import Dict, List, Any, Union

# Fields to combine into searchable_text, by primary_issue
SEARCHABLE_FIELDS: Dict[str, List[str]] = {
    'common': [
        'dataset_name',
        'comments',
        'observation',
        'description',
        'name',
        'title',
        'address',
    ],
    'health': [
        'beachName',
        'estName',
        'siteName',
        'defDesc',
        'establishment_name',
        'establishment_type',
        'establishment_address',
        'infraction_details',
        'institution_name',
        'institution_address',
        'outbreak_type',
        'causative_agent_1',
    ],
    'housing': [
        'full_address',
        'street_name',
        'street_no',
        'property_type',
        'ward_name',
        'neighbourhood',
        # Handle both snake_case and original case
        'Street_Name',
        'Street_No',
    ],
    'transportation': [
        'station_name',
        'route_name',
        'street_name',
        'intersection',
        'location_name',
    ],
    'environment': [
        'park_name',
        'facility_name',
        'location_name',
        'site_name',
    ],
}


def build_searchable_text(doc: Dict[str, Any]) -> str:
    """
    Build comprehensive searchable_text from document fields.
    
    Args:
        doc: MongoDB/ES document
    
    Returns:
        Combined searchable text string
    """
    text_parts: List[str] = []
    
    primary_issue = doc.get('primary_issue', '')
    
    # Common fields
    for field in SEARCHABLE_FIELDS['common']:
        value = doc.get(field)
        if value and isinstance(value, str) and value.strip():
            text_parts.append(value.strip())
    
    # Issue-specific fields
    if primary_issue in SEARCHABLE_FIELDS:
        for field in SEARCHABLE_FIELDS[primary_issue]:
            value = doc.get(field)
            if value:
                if isinstance(value, str) and value.strip():
                    text_parts.append(value.strip())
                elif isinstance(value, (int, float)):
                    text_parts.append(str(value))
    
    # ─────────────────────────────────────────────────────────────────────────
    # 3. KEYWORDS AND METADATA
    # ─────────────────────────────────────────────────────────────────────────
    # Include issue_keywords (important for search!)
    keywords = doc.get('issue_keywords', [])
    if keywords and isinstance(keywords, list):
        text_parts.extend([k for k in keywords if isinstance(k, str)])
    
    # Include dataset_id as searchable terms
    dataset_id = doc.get('dataset_id', '')
    if dataset_id:
        text_parts.append(dataset_id.replace('-', ' ').replace('_', ' '))
    
    # Include subcategory
    subcategory = doc.get('subcategory', '')
    if subcategory:
        text_parts.append(subcategory.replace('_', ' '))
    
    # Include primary_issue and secondary_issues
    if primary_issue:
        text_parts.append(primary_issue)
    
    secondary_issues = doc.get('secondary_issues', [])
    if secondary_issues and isinstance(secondary_issues, list):
        text_parts.extend(secondary_issues)
    
    # Join and clean
    searchable_text = ' '.join(text_parts)
    searchable_text = ' '.join(searchable_text.split())  # Remove extra whitespace
    
    return searchable_text

def get_fields_for_issue(primary_issue: str) -> List[str]:
    """
    Get all searchable fields for a given issue type.
    
    Args:
        primary_issue: The primary issue category
        
    Returns:
        Combined list of common + issue-specific fields
    """
    fields = SEARCHABLE_FIELDS['common'].copy()
    
    if primary_issue in SEARCHABLE_FIELDS:
        fields.extend(SEARCHABLE_FIELDS[primary_issue])
    
    return fields

