
from urllib.parse import urlparse
import re
import os

def get_base_path(url):
    """
    Extract a meaningful filename from the URL.
    Falls back to parliament_votes if nothing found.
    """
    # Parse the URL
    parsed = urlparse(url)
    path = parsed.path
    
    # Remove format extensions from path
    for fmt in ['/csv', '/xml', '/json', '.csv', '.xml', '.json']:
        if path.lower().endswith(fmt):
            path = path[:-len(fmt)]
            break
    
    # Remove query parameters that specify format
    query = parsed.query
    if query:
        # Remove format-related query params
        query_parts = [p for p in query.split('&') 
                      if not any(f in p.lower() for f in ['output=', 'format=', 'xml='])]
        query = '&'.join(query_parts) if query_parts else ''
    
    # Reconstruct base URL
    base_url = f"{parsed.scheme}://{parsed.netloc}{path}"
    if query:
        base_url += f"?{query}"
    
    return base_url

def get_filename_from_url(url, format_type):
    """
    Extract a meaningful filename from the URL.
    Falls back to parliament_votes if nothing found.
    
    Args:
        url (str): The URL to extract filename from
        format_type (str): File extension (csv, json, xml)
    
    Returns:
        str: Generated filename with extension
    
    Examples:
        >>> get_filename_from_url('https://example.com/members/en/votes/csv', 'csv')
        'votes.csv'
        >>> get_filename_from_url('https://example.com/data/parliament_2024.csv', 'csv')
        'parliament_2024.csv'
    """
    try:
        # Parse the URL
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        if not path:
            return f"parliament_votes.{format_type}"
        
        # Split path into parts
        parts = path.split('/')
        
        # Get the last part of the path
        last_part = parts[-1] if parts else ''
        
        # Case 1: URL ends with format type (e.g., /votes/csv)
        if last_part.lower() == format_type:
            # Use the second-to-last part if available
            if len(parts) >= 2:
                return f"{parts[-2]}.{format_type}"
            return f"data.{format_type}"
        
        # Case 2: Last part has a file extension
        if '.' in last_part:
            base_name = last_part.rsplit('.', 1)[0]
            return f"{base_name.lower()}.{format_type}"
        
        # Case 3: Last part is meaningful (not just numbers or format type)
        if last_part and not last_part.isdigit():
            return f"{last_part.lower()}.{format_type}"
        
        # Case 4: Build filename from path
        # Remove common prefixes and build meaningful name
        cleaned_parts = []
        skip_prefixes = {'members', 'api', 'data', 'export', 'en', 'fr'}
        
        for part in parts:
            part_lower = part.lower()
            # Skip common prefixes and format types
            if part_lower not in skip_prefixes and part_lower != format_type:
                # Keep meaningful parts (not just numbers)
                if not part.isdigit() or len(cleaned_parts) > 0:
                    cleaned_parts.append(part_lower)
  
        if cleaned_parts:
            # Join with underscore, limit to last 3 parts for readability
            filename_base = '_'.join(cleaned_parts[-3:])
            return f"{filename_base.lower()}.{format_type}"
        
    except Exception as e:
        print(f'  ✗ Error extracting filename: {type(e).__name__}: {str(e)}')
        return f"parliament_votes.{format_type}"
    


def ensure_directory_exists(directory):
    """
    Create directory if it doesn't exist.
    
    Args:
        directory (str): Path to directory
    """
    os.makedirs(directory, exist_ok=True)


def file_exists_prompt(filepath):
    """
    Check if file exists and return a message.
    
    Args:
        filepath (str): Path to file
    
    Returns:
        bool: True if file exists
    """
    return os.path.exists(filepath)