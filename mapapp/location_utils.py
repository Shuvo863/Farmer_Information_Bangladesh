import json
import os
import threading
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def normalize_bn_name(s):
    """Robust normalization for Bengali names to handle Unicode and spelling variations"""
    if not s: return ""
    s = str(s).strip().replace(" ", "")
    # Standardize common character variations
    s = s.replace('\u09af\u09bc', '\u09df') # য+dot -> য়
    s = s.replace('\u09a2\u09bc', '\u09dc').replace('\u09a1\u09bc', '\u09dc') # ঢ/ড+dot -> ড়
    s = s.replace('\u09a3', '\u09a8') # ণ -> ন
    s = s.replace('\u09c0', '\u09bf') # ী -> ি
    s = s.replace('\u09c2', '\u09c1') # ূ -> ু
    s = s.replace('\u09b7', '\u09b6').replace('\u09b8', '\u09b6') # ষ, স -> শ
    s = s.replace('\u0981', '') # Remove Chandrabindu (ঁ) for more robust matching
    s = s.replace('\u09a7', '\u09a6') # ধ -> দ (Common phonetic variations)
    s = s.replace('\u09a5', '\u09a4') # থ -> ত
    # Handle Sadar
    if s.endswith('সদর') and len(s) > 3:
        return s[:-3] + ' সদর'
    return s

def levenshtein_distance(a, b):
    """Simple Levenshtein distance implementation"""
    if len(a) < len(b):
        return levenshtein_distance(b, a)
    if len(b) == 0:
        return len(a)
    
    previous_row = range(len(b) + 1)
    for i, c1 in enumerate(a):
        current_row = [i + 1]
        for j, c2 in enumerate(b):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

class LocationMapper:
    """Manages mapping between Database location names and GeoJSON identifiers."""
    _instance = None
    
    def __init__(self):
        self.en_to_db = {'districts': {}, 'upazilas': {}} # Map name_en -> list of DB names
        self.db_to_en = {'districts': {}, 'upazilas': {}} # Map DB name -> Map name_en
        self.division_to_districts = {} # Map division_en -> list of English district names
        self.initialized = False
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self):
        if self.initialized: return
        with self._lock:
            if self.initialized: return
            try:
                print("Initializing LocationMapper...")
                # Deferred import to avoid circular dependency
                from .db_utils import get_distinct_options_from_db
                db_options = get_distinct_options_from_db()
                db_districts = db_options.get('districts', [])
                db_upazilas = db_options.get('upazilas', [])
                
                geojson_dir = os.path.join(settings.BASE_DIR, 'geojson_data')
                
                # Load Districts
                with open(os.path.join(geojson_dir, 'districts.geojson'), 'r', encoding='utf-8') as f:
                    d_data = json.load(f)
                    geo_districts = [feat['properties'] for feat in d_data['features']]
                    for prop in geo_districts:
                        div = prop.get('division_en')
                        dist = prop.get('name_en')
                        if div:
                            if div not in self.division_to_districts:
                                self.division_to_districts[div] = []
                            if dist not in self.division_to_districts[div]:
                                self.division_to_districts[div].append(dist)

                for db_name in db_districts:
                    best_match = self._find_best_match(db_name, geo_districts)
                    if best_match:
                        en_name = best_match['name_en']
                        if en_name not in self.en_to_db['districts']:
                            self.en_to_db['districts'][en_name] = []
                        self.en_to_db['districts'][en_name].append(db_name)
                        self.db_to_en['districts'][normalize_bn_name(db_name)] = en_name

                # Load Upazilas
                with open(os.path.join(geojson_dir, 'upazilas.geojson'), 'r', encoding='utf-8') as f:
                    u_data = json.load(f)
                    geo_upazilas = [feat['properties'] for feat in u_data['features']]
                for db_name in db_upazilas:
                    best_match = self._find_best_match(db_name, geo_upazilas)
                    if best_match:
                        en_name = best_match['name_en']
                        if en_name not in self.en_to_db['upazilas']:
                            self.en_to_db['upazilas'][en_name] = []
                        self.en_to_db['upazilas'][en_name].append(db_name)
                        self.db_to_en['upazilas'][normalize_bn_name(db_name)] = en_name
                
                self.initialized = True
                print(f"LocationMapper initialized successfully. Districts: {len(self.en_to_db['districts'])}, Upazilas: {len(self.en_to_db['upazilas'])}")
            except Exception as e:
                print(f"Error initializing LocationMapper: {e}")
                logger.error(f"Error initializing LocationMapper: {e}")
                pass

    def _find_best_match(self, db_name, geo_props_list):
        db_norm = normalize_bn_name(db_name)
        for p in geo_props_list:
            if normalize_bn_name(p.get('name_bn')) == db_norm:
                return p
        best_p, min_dist = None, 999
        for p in geo_props_list:
            geo_norm = normalize_bn_name(p.get('name_bn'))
            dist = levenshtein_distance(db_norm, geo_norm)
            if dist < min_dist:
                min_dist, best_p = dist, p
        threshold = max(1, int(len(db_norm) * 0.35))
        return best_p if min_dist <= threshold else None

    def get_db_names(self, entity_type, en_name):
        if not self.initialized: self.initialize()
        return self.en_to_db.get(entity_type, {}).get(en_name, [en_name])

    def get_en_name(self, entity_type, db_name):
        if not self.initialized: self.initialize()
        return self.db_to_en.get(entity_type, {}).get(normalize_bn_name(db_name))

    def get_districts_for_division(self, division_en):
        if not self.initialized: self.initialize()
        return self.division_to_districts.get(division_en, [])
