# config/taxonomy.py

ISSUE_TAXONOMY = {
    "health": {
        "description": "Public health, healthcare access, disease prevention",
        "keywords": ["health", "hospital", "medical", "disease", "inspection", "safety", "hygiene", 
                     "bodysafe", "e.coli", "bacteria", "outbreak", "clinic", "healthcare"],
        "subcategories": {
            "water_quality": {
                "keywords": ["beach", "water", "e.coli", "swimming", "lake", "bacteria"],
                "datasets": ["toronto-beaches-water-quality", "toronto-beaches-observations"]
            },
            "food_safety": {
                "keywords": ["dinesafe", "restaurant", "food", "inspection", "kitchen"],
                "datasets": ["dinesafe"]
            },
            "personal_services": {
                "keywords": ["bodysafe", "aesthetics", "tattoo", "spa", "salon", "sterilization"],
                "datasets": ["bodysafe"]
            },
            "mental_health": {
                "keywords": ["opioid", "overdose", "addiction", "mental", "shelter"],
                "datasets": ["fatal-and-non-fatal-suspected-opioid-overdoses-in-the-shelter-system"]
            },
            "outbreaks": {
                "keywords": ["outbreak", "infection", "communicable", "disease", "healthcare"],
                "datasets": ["outbreaks-in-toronto-healthcare-institutions", 
                             "annual-summary-of-reportable-communicable-diseases"]
            },

        }
    },
    "transportation": {
        "description": "Public transit, roads, cycling, traffic management",
        "keywords": ["transit", "ttc", "subway", "bus", "traffic", "road", "cycling", "bike", 
                     "pedestrian", "intersection", "speed", "signal"],
        "subcategories": {
            "traffic_management": {
                "keywords": ["traffic", "signal", "intersection", "speed", "volume"],
                "datasets": ["traffic-volumes-at-intersections-for-all-modes", 
                            "traffic-signal-timing", "traffic-volumes-midblock-vehicle-speed-volume-and-classification-counts"]
            },
            "road_safety": {
                "keywords": ["red-light", "camera", "safety", "collision", "accident"],
                "datasets": ["red-light-cameras", "safety-zone-watch-your-speed-program-monthly-summary",
                             "red-light-camera-annual-charges" ]
            },
            "cycling": {
                "keywords": ["bike", "cycling", "bicycle", "trail"],
                "datasets": ["street-furniture-bicycle-parking", "10-year-cycling-network-plan-trails-2016"]
            },
            "infrastructure": {
                "keywords": ["sidewalk", "road", "construction", "centreline"],
                "datasets": ["sidewalk-construction-program", "toronto-centreline-tcl"]
            }
        }
    },
    "environment": {
        "description": "Climate, sustainability, parks, natural areas",
        "keywords": ["environment", "climate", "green", "park", "tree", "energy", "renewable", 
                     "emission", "pollution", "ravine", "nature"],
        "subcategories": {
            "energy": {
                "keywords": ["energy", "renewable", "solar", "consumption", "electricity"],
                "datasets": ["renewable-energy-installations", "annual-energy-consumption"]
            },
            "natural_areas": {
                "keywords": ["ravine", "park", "nature", "forest", "trail"],
                "datasets": ["ravine-natural-feature-protection-area", "parks-drinking-fountains"]
            },
            "water_environment": {
                "keywords": ["beach", "lake", "water", "observation"],
                "datasets": ["toronto-beaches-observations"]
            }
        }
    },
    "housing": {
        "description": "Affordable housing, rental, homelessness, shelter",
        "keywords": ["housing", "rental", "apartment", "shelter", "homeless", "affordable", 
                    "tenant", "landlord", "eviction", "benefit",
                    "subsidy", "supportive housing", "property tax", "seniors"
        ],
        "subcategories": {
            "rental_housing": {
                "keywords": ["apartment", "rental", "building", "tenant"],
                "datasets": ["apartment-building-registration"]
            },
            "shelter": {
                "keywords": ["shelter", "homeless", "emergency"],
                "datasets": ["fatal-and-non-fatal-suspected-opioid-overdoses-in-the-shelter-system"]
            },
            "condominiums": {
                "keywords": ["condo", "condominium", "registered"],
                "datasets": ["registered-residential-non-residential-condominiums"]
            },
            "housing_to_plan": {
                "keywords": [
                    "HousingTO", "strategy", "targets", "evictions prevented",
                    "supportive homes", "MURA", "CHPR", "portable benefits"
                ],
                "datasets": ["housing-to-action-plan"]
            },
            
        }
    },
    "public_safety": {
        "description": "Crime, policing, emergency services",
        "keywords": ["police", "crime", "safety", "emergency", "fire", "ambulance", "911"],
        "subcategories": {
            "crime": {
                "keywords": ["crime", "police", "theft", "assault", "robbery"],
                "datasets": ["police-annual-statistical-report-reported-crimes"]
            }
        }
    },
    "poverty_reduction": {
        "description": "Income inequality, social assistance, food security",
        "keywords": ["poverty", "low-income", "inequality", "food", "assistance", "welfare", "odsp"],
        "subcategories": {}
    },
    "business_and_economy": {
        "description": "Business, employment, economic development",
        "keywords": ["business", "employment", "economy", "commercial", "job", "workforce"],
        "subcategories": {
            "employment": {
                "keywords": ["employment", "job", "workforce", "labour"],
                "datasets": ["toronto-employment-survey-summary-tables"]
            }
        }
    }
}

# Dataset to Issue Mapping (explicit mapping)
DATASET_ISSUE_MAP = {
    # Health
    "outbreaks-in-toronto-healthcare-institutions": {"primary": "health", "secondary": [], "subcategory": "outbreaks"},
    "annual-summary-of-reportable-communicable-diseases": {"primary": "health", "secondary": [], "subcategory": "communicable-diseases"},
    "toronto-population-health-status-indicators": {"primary": "health", "secondary": ["demographics"], "subcategory": "population-health"},
    "toronto-beaches-water-quality": {"primary": "health", "secondary": ["environment"], "subcategory": "water_quality"},
    "toronto-beaches-observations": {"primary": "environment", "secondary": ["health"], "subcategory": "water_environment"},
    "bodysafe": {"primary": "health", "secondary": [], "subcategory": "personal_services"},
    "dinesafe": {"primary": "health", "secondary": [], "subcategory": "food_safety"},
    "chemical-tracking-chemtrac": {"primary": "health", "secondary": ["environment"], "subcategory": "chemical_safety"},
    "fatal-and-non-fatal-suspected-opioid-overdoses-in-the-shelter-system": {"primary": "health", "secondary": ["housing", "poverty_reduction"], "subcategory": "mental_health"},
    
    #housing
    "apartment-building-registration": {"primary": "housing", "secondary": [], "subcategory": "rental_housing"},
    "registered-residential-non-residential-condominiums": {"primary": "housing", "secondary": [], "subcategory": "condominiums"},  
    "housing-to-action-plan": { "primary": "housing", "secondary": ["poverty_reduction", "health"],"subcategory": "housing_to_plan"},
    #business and economy
    "toronto-employment-survey-summary-tables": {"primary": "business_and_economy", "secondary": ["demographics"], "subcategory": "employment"},
    # Transportation
    "traffic-volumes-at-intersections-for-all-modes": {"primary": "transportation", "secondary": [], "subcategory": "traffic_management"},
    "traffic-signal-timing": {"primary": "transportation", "secondary": [], "subcategory": "traffic_management"},
    "red-light-cameras": {"primary": "transportation", "secondary": ["public_safety"], "subcategory": "road_safety"},
    "red-light-camera-annual-charges": { "primary": "transportation", "secondary": ["public_safety"],"subcategory": "road_safety"},
    "street-furniture-bicycle-parking": {"primary": "transportation", "secondary": [], "subcategory": "cycling"},
    "sidewalk-construction-program": {"primary": "transportation", "secondary": [], "subcategory": "infrastructure"},
    "safety-zone-watch-your-speed-program-monthly-summary": {"primary": "transportation", "secondary": ["public_safety"], "subcategory": "road_safety"},
    
    # Environment
    "renewable-energy-installations": {"primary": "environment", "secondary": [], "subcategory": "energy"},
    "annual-energy-consumption": {"primary": "environment", "secondary": [], "subcategory": "energy"},
    "ravine-natural-feature-protection-area": {"primary": "environment", "secondary": [], "subcategory": "natural_areas"},
    "parks-drinking-fountains": {"primary": "environment", "secondary": ["health"], "subcategory": "natural_areas"},

    # Safety datasets
    "police-annual-statistical-report": {"primary": "safety","secondary": [],"subcategory": "crime-statistics"},
    "fire-incidents": {"primary": "safety","secondary": [],"subcategory": "fire-services"},
}