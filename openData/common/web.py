import os
import requests
from typing import List, Dict, Any



def fetch_json_from_url(url: str) -> List[Dict[str, Any]]:
    """Fetch and parse JSON from a direct URL"""
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    
    # Normalize to list of records
    if isinstance(data, dict):
        # Check if it's a wrapper with a data field
        if "data" in data and isinstance(data["data"], list):
            return data["data"]
        elif "records" in data and isinstance(data["records"], list):
            return data["records"]
        elif "results" in data and isinstance(data["results"], list):
            return data["results"]
        else:
            # Single record
            return [data]
    elif isinstance(data, list):
        return data
    else:
        raise ValueError(f"Unexpected JSON format: {type(data)}")

def fetch_datastore_records(base_url: str, resource_id: str, limit: int = 32000) -> list:
    """Fetch all records from CKAN datastore API with pagination"""
    url = f"{base_url}/api/3/action/datastore_search"
    
    all_records = []
    offset = 0
    
    while True:
        params = {"id": resource_id, "limit": limit, "offset": offset}
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        records = response.json()["result"].get("records", [])
        if not records:
            break
        
        all_records.extend(records)
        offset += limit
        
        if len(records) < limit:
            break
    
    return all_records


def fetch_package_metadata(base_url: str, package_name: str) -> dict:
    """Fetch package/dataset metadata from CKAN API"""
    url = f"{base_url}/api/3/action/package_show"
    response = requests.get(url, params={"id": package_name})
    response.raise_for_status()
    return response.json()["result"]


# __all__ = [
#     'download_file',
#     'fetch_json_from_url',
#     'fetch_datastore_records',
#     'fetch_package_metadata'
# ]