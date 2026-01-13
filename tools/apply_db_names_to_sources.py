#!/usr/bin/env python3
"""
Apply DB canonical names from `exact_matches.xlsx` to GeoJSON and population Excel.

Behavior:
- Read `exact_matches.xlsx` and build a mapping keyed by district_en -> sets of
  (upazila_db, upazila_geojson, upazila_excel).
- Backup `geojson_data/upazilas.geojson` -> `.bak` and replace matching feature
  names (prefer matching on `name_bn`, `name_en`, `ADM3_BN`, `ADM3_EN`) by setting
  the chosen DB name into `properties['name_bn']` (keeps other fields untouched).
- Backup `upazila_population.xlsx` -> `.bak` and update the detected Upazila column
  values where they match geo/excel strings, replacing with the DB name.

The script prints summary counts and writes changed files in-place.
"""
import os
import json
from collections import defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
EXACT = os.path.join(BASE, 'exact_matches.xlsx')
GEO = os.path.join(BASE, 'geojson_data', 'upazilas.geojson')
GEO_BAK = GEO + '.bak'
POP_XLSX = os.path.join(BASE, 'upazila_population.xlsx')
POP_BAK = POP_XLSX + '.bak'


def build_mapping():
    """Return mapping: district_en -> list of tuples (db, geo, excel) and flat lookup maps."""
    try:
        import pandas as pd
    except Exception:
        print('pandas required')
        return {}, {}, {}
    if not os.path.exists(EXACT):
        print('exact_matches.xlsx not found:', EXACT)
        return {}, {}, {}
    df = pd.read_excel(EXACT)
    # normalize column names
    cols = {c.lower(): c for c in df.columns}
    dcol = cols.get('district_en')
    dbcol = cols.get('upazila_db')
    geocol = cols.get('upazila_geojson')
    excol = cols.get('upazila_excel')
    mapping = defaultdict(list)
    geo_lookup = {}  # map geo_name -> db_name (choose first matching)
    excel_lookup = {}
    for _, r in df.iterrows():
        d = str(r[dcol]).strip() if dcol and not pd.isna(r[dcol]) else ''
        db = str(r[dbcol]).strip() if dbcol and not pd.isna(r[dbcol]) else ''
        g = str(r[geocol]).strip() if geocol and not pd.isna(r[geocol]) else ''
        e = str(r[excol]).strip() if excol and not pd.isna(r[excol]) else ''
        if d and db:
            mapping[d].append((db, g, e))
            if g:
                geo_lookup[g] = db
            if e:
                excel_lookup[e] = db
    return mapping, geo_lookup, excel_lookup


def update_geojson(geo_lookup):
    if not os.path.exists(GEO):
        print('GeoJSON not found:', GEO)
        return 0
    # backup
    if not os.path.exists(GEO_BAK):
        os.rename(GEO, GEO_BAK)
        with open(GEO_BAK, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # work on data then write to GEO path
    else:
        with open(GEO_BAK, 'r', encoding='utf-8') as f:
            data = json.load(f)

    changed = 0
    for feat in data.get('features', []):
        props = feat.get('properties', {})
        # possible name fields
        candidates = []
        for key in ('name_bn', 'name_en', 'ADM3_BN', 'ADM3_EN', 'NAME_BN', 'NAME_EN'):
            v = props.get(key)
            if v:
                candidates.append((key, str(v).strip()))
        replaced = False
        for key, val in candidates:
            if val in geo_lookup:
                db_name = geo_lookup[val]
                # set Bengali name field to DB name (keeping casing)
                props['name_bn'] = db_name
                changed += 1
                replaced = True
                break
        if replaced:
            feat['properties'] = props

    # write updated geojson
    with open(GEO, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    return changed


def update_excel(excel_lookup):
    try:
        import pandas as pd
    except Exception:
        print('pandas required to update Excel')
        return 0
    if not os.path.exists(POP_XLSX):
        print('Population Excel not found:', POP_XLSX)
        return 0
    # backup
    if not os.path.exists(POP_BAK):
        import shutil
        shutil.copy2(POP_XLSX, POP_BAK)

    df = pd.read_excel(POP_XLSX)
    col_names = {c.lower(): c for c in df.columns}
    up_col = None
    for name in ['upazila', 'উপজেলা', 'upazila_bn', 'upazila_name']:
        if name.lower() in col_names:
            up_col = col_names[name.lower()]
            break
    if not up_col:
        print('Could not detect Upazila column in Excel. Columns:', list(df.columns))
        return 0

    changed = 0
    for idx, row in df.iterrows():
        val = row[up_col]
        if pd.isna(val):
            continue
        s = str(val).strip()
        if s in excel_lookup:
            df.at[idx, up_col] = excel_lookup[s]
            changed += 1
        elif s in geo_lookup:
            df.at[idx, up_col] = geo_lookup[s]
            changed += 1

    df.to_excel(POP_XLSX, index=False)
    return changed


if __name__ == '__main__':
    mapping, geo_lookup, excel_lookup = build_mapping()
    if not mapping:
        print('No mapping found in exact_matches.xlsx — aborting')
        raise SystemExit(1)
    print('Mapping districts:', len(mapping), 'geo keys:', len(geo_lookup), 'excel keys:', len(excel_lookup))
    g_changed = update_geojson(geo_lookup)
    print('GeoJSON features updated:', g_changed)
    e_changed = update_excel(excel_lookup)
    print('Excel rows updated:', e_changed)
