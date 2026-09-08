# transformers.py

from datetime import datetime
from typing import Dict, Any


def _derive_ins_date(doc: Dict[str, Any]) -> str | None:
    """
    Pick a unified insDate field from dataset-specific date fields.
    Returned as 'YYYY-MM-DD' or None.
    """
    # Daily shelter – occupancy_date like "2019-01-01T00:00:00" or "01/01/2020"

    dataset_id = doc.get("dataset_id")

    # Shelter dataset
    if dataset_id == "daily-shelter-occupancy":
        raw = doc.get("occupancy_date")
        if isinstance(raw, str):
            # "2019-01-01T00:00:00"
            if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
                return raw[:10]
            # "01/01/2020" -> "2020-01-01"
            if len(raw) == 10 and raw[2] == "/" and raw[5] == "/":
                try:
                    dt = datetime.strptime(raw, "%m/%d/%Y")
                    return dt.strftime("%Y-%m-%d")
                except Exception:
                    return None

    # Outbreaks dataset
    if dataset_id == "outbreaks-in-toronto-healthcare-institutions":
        raw = doc.get("date_outbreak_began") or doc.get("data_collection_date")
        if isinstance(raw, str) and len(raw) >= 10:
            return raw[:10]

    # Generic fallback
    raw = doc.get("data_collection_date")
    if isinstance(raw, str) and len(raw) >= 10:
        return raw[:10]

    return None


def transform_shelter(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform daily-shelter-occupancy Mongo doc → ES doc.
    Keeps key policy fields plus all date fields we care about.
    """
    # unique id for ES
    unique_id = doc.get("_unique_id") or str(doc.get("_id"))

    es_doc = {
        "_unique_id": unique_id,
        "doc_id": unique_id,
        "dataset_id": doc.get("dataset_id", "daily-shelter-occupancy"),

        "primary_issue": doc.get("primary_issue", "housing"),
        "secondary_issues": doc.get("secondary_issues", []),
        "subcategory": doc.get("subcategory", "shelter"),
        "data_type": doc.get("data_type", "record"),
        "issue_keywords": doc.get("issue_keywords", []),
        "searchable_text": doc.get("searchable_text"),

        # Capacity/occupancy fields
       
        "occupancy_date": doc.get("occupancy_date"),
        "capacity": doc.get("capacity"),
        "occupancy": doc.get("occupancy"),
        # Shelter metadata
        "shelter_name": doc.get("shelter_name"),
        "facility_name": doc.get("facility_name"),
        "sector": doc.get("sector"),
        "shelter_address": doc.get("shelter_address"),
        "shelter_city": doc.get("shelter_city"),
        "shelter_postal_code": doc.get("shelter_postal_code"),
        "shelter_province": doc.get("shelter_province"),
        "organization_name": doc.get("organization_name"),
        "program_name": doc.get("program_name"),

        # Original date fields (keep for debugging/analytics)
        "data_collection_date": doc.get("data_collection_date"),
    }

    keywords = es_doc.get("issue_keywords") or []
    if "tenant" not in keywords:
        keywords.append("tenant")
    es_doc["issue_keywords"] = keywords

    if es_doc.get("searchable_text"):
        if "tenant" not in es_doc["searchable_text"].lower():
            es_doc["searchable_text"] += " tenant"
    else:
        es_doc["searchable_text"] = "tenant"
        
    ins_date = _derive_ins_date(es_doc)
    if ins_date:
        es_doc["insDate"] = ins_date

    return es_doc


def transform_outbreak(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform outbreaks Mongo doc → ES doc.
    """
    unique_id = doc.get("_unique_id") or str(doc.get("_id"))

    es_doc = {
        "_unique_id": unique_id,
        "doc_id": unique_id,
        "dataset_id": doc.get("dataset_id", "outbreaks-in-toronto-healthcare-institutions"),
        
        "primary_issue": doc.get("primary_issue", "health"),
        "secondary_issues": doc.get("secondary_issues", []),
        "subcategory": doc.get("subcategory"),
        "data_type": doc.get("data_type", "record"),
        "issue_keywords": doc.get("issue_keywords", []),
        "searchable_text": doc.get("searchable_text"),

        # Outbreak dates
        "date_outbreak_began": doc.get("date_outbreak_began"),
        "date_declared_over": doc.get("date_declared_over"),
        "data_collection_date": doc.get("data_collection_date"),
    }

    ins_date = _derive_ins_date(es_doc)
    if ins_date:
        es_doc["insDate"] = ins_date

    return es_doc


def transform_generic(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generic transformer for other policy datasets (DineSafe, beaches, etc.).
    Keeps core policy fields + unified insDate.
    """
    unique_id = doc.get("_unique_id") or str(doc.get("_id"))

    es_doc = {
        "_unique_id": unique_id,
        "doc_id": unique_id,
        "dataset_id": doc.get("dataset_id"),

        "primary_issue": doc.get("primary_issue", "uncategorized"),
        "secondary_issues": doc.get("secondary_issues", []),
        "subcategory": doc.get("subcategory"),
        "data_type": doc.get("data_type"),
        "issue_keywords": doc.get("issue_keywords", []),
        "searchable_text": doc.get("searchable_text"),

        # Common date-ish fields
        "data_collection_date": doc.get("data_collection_date"),
        "collectionDate": doc.get("collectionDate"),
    }

    ins_date = _derive_ins_date(es_doc)
    if ins_date:
        es_doc["insDate"] = ins_date

    return es_doc


def transform_red_light_charges(doc: Dict[str, Any]) -> Dict[str, Any]:
    unique_id = doc.get("_unique_id") or str(doc.get("_id"))

    es_doc = {
        "_unique_id": unique_id,
        "doc_id": unique_id,
        "dataset_id": doc.get("dataset_id", "red-light-camera-annual-charges"),

        "primary_issue": doc.get("primary_issue", "transportation"),
        "secondary_issues": doc.get("secondary_issues", ["public_safety"]),
        "subcategory": doc.get("subcategory", "road_safety"),
        "data_type": doc.get("data_type", "record"),
        "issue_keywords": doc.get("issue_keywords", []),
        "searchable_text": doc.get("searchable_text"),

        "location_code": doc.get("location_code"),
        "ward_number": doc.get("ward_number"),
        "location_name": doc.get("location_name"),
        "year": doc.get("year"),
        "charges": doc.get("charges"),
        "enforcement_start_date": doc.get("enforcement_start_date"),
        "enforcement_end_date": doc.get("enforcement_end_date"),
    }

    ins_date = _derive_ins_date(es_doc)
    if ins_date:
        es_doc["insDate"] = ins_date

    return es_doc
