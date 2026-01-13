import json
import os
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.conf import settings
from .db_utils import (
    get_farmers_from_db, get_distinct_options_from_db,
    get_field_forces_from_db, get_area_stats_from_db, 
    get_population_cover_data, get_gender_stats_from_db,
    get_land_stats_from_db, get_class_stats_from_db,
    get_common_stats_from_db, get_land_amount_bins_from_db
)
from .location_utils import normalize_bn_name, LocationMapper, levenshtein_distance
import re

import threading
import logging
logger = logging.getLogger(__name__)

def build_filters(request):
    """Common logic for building filters from request parameters"""
    division_filter = request.GET.get('division')
    district_filter = request.GET.get('district') # English
    upazila_filter = request.GET.get('upazila')  # English
    
    mapper = LocationMapper.get_instance()
    geojson_dir = os.path.join(settings.BASE_DIR, 'geojson_data')
    
    district_list = []
    if district_filter:
        district_list = mapper.get_db_names('districts', district_filter)
    
    upazila_list = []
    if upazila_filter:
        upazila_list = mapper.get_db_names('upazilas', upazila_filter)

    # If division is filtered but district is not, get all districts in that division
    if division_filter and not district_filter:
        dist_en_list = mapper.get_districts_for_division(division_filter)
        for en_name in dist_en_list:
            district_list.extend(mapper.get_db_names('districts', en_name))

    filters = {
        'class': request.GET.get('class'),
        'gender': request.GET.get('gender'),
        'education': request.GET.get('education'),
        'smart_phone': request.GET.get('smart_phone'),
        'search': request.GET.get('search', '').strip(),
        'land_operator': request.GET.get('land_operator'),
        'land_amount': request.GET.get('land_amount')
    }

    # Only include geographic lists if a map/geographic filter was requested
    if division_filter or district_filter:
        filters['district_list'] = district_list
    if upazila_filter:
        filters['upazila_list'] = upazila_list

    return {k: v for k, v in filters.items() if v is not None and v != ''}



def is_fuzzy_match(base, target, threshold=None):
    if not base or not target: return False
    
    # Pre-process: lower and remove padding
    base = base.strip().lower()
    target = target.strip().lower()
    
    # Handle "Town" or "Down" -> "Sadar"
    # Some field force bases use "Down" (misspelling of Town) or "Town" for "Sadar"
    base = base.replace('down', 'sadar').replace('town', 'sadar')
    target = target.replace('down', 'sadar').replace('town', 'sadar')
    
    if base == target: return True
    
    # Space-insensitive check
    base_no_space = base.replace(' ', '')
    target_no_space = target.replace(' ', '')
    if base_no_space == target_no_space: return True
    
    if threshold is None:
        # Tighten threshold: approx 25% of length, minimum 1
        threshold = max(1, int(len(target) * 0.25))
        
    return levenshtein_distance(base_no_space, target_no_space) <= threshold

def index(request):
    """Main map view"""
    return render(request, 'mapapp/index.html')

def analytics(request):
    """Analytics view"""
    return render(request, 'mapapp/analytics.html')

def get_geojson(request, layer_type):
    """Serve GeoJSON files"""
    geojson_dir = os.path.join(settings.BASE_DIR, 'geojson_data')
    
    file_map = {
        'divisions': 'divisions.geojson',
        'districts': 'districts.geojson',
        'upazilas': 'upazilas.geojson'
    }
    
    filename = file_map.get(layer_type)
    if not filename:
        return JsonResponse({'error': 'Invalid layer type'}, status=400)
        
    try:
        file_path = os.path.join(geojson_dir, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Filter Logic (Simulated for simpler files like districts/upazilas)
        # For a real implementation with large files, we'd use a spatial database (PostGIS)
        # Here we just filter the features list if requested
        
        division_filter = request.GET.get('division')
        district_filter = request.GET.get('district')
        
        if division_filter or district_filter:
            filtered_features = []
            for feature in data['features']:
                props = feature['properties']
                include = True
                
                # Filter by Division
                if division_filter:
                    if props.get('division_en') != division_filter:
                        include = False
                        
                # Filter by District (only relevant for upazilas layer usually)
                if district_filter:
                    if props.get('district_en') != district_filter:
                        include = False
                        
                if include:
                    filtered_features.append(feature)
            
            data['features'] = filtered_features
            
        return JsonResponse(data)
    except FileNotFoundError:
        return JsonResponse({'error': 'GeoJSON file not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_divisions(request):
    """Get list of divisions"""
    geojson_dir = os.path.join(settings.BASE_DIR, 'geojson_data')
    try:
        with open(os.path.join(geojson_dir, 'divisions.geojson'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        divisions = []
        for feat in data['features']:
            props = feat['properties']
            divisions.append({
                'name_en': props.get('name_en'),
                'name_bn': props.get('name_bn'),
                'id': props.get('id')
            })
            
        # Sort by name
        divisions.sort(key=lambda x: x['name_en'])
        
        return JsonResponse({'divisions': divisions})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_districts(request):
    """Get list of districts, optionally filtered by division"""
    division_name = request.GET.get('division')
    geojson_dir = os.path.join(settings.BASE_DIR, 'geojson_data')
    
    try:
        with open(os.path.join(geojson_dir, 'districts.geojson'), 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        districts = []
        for feat in data['features']:
            props = feat['properties']
            
            if division_name and props.get('division_en') != division_name:
                continue
                
            districts.append({
                'name_en': props.get('name_en'),
                'name_bn': props.get('name_bn', '').strip(),
                'division_en': props.get('division_en')
            })
            
        districts.sort(key=lambda x: x['name_en'])
        return JsonResponse({'districts': districts})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_upazilas(request):
    """Get list of upazilas, optionally filtered by district"""
    district_name = request.GET.get('district')
    geojson_dir = os.path.join(settings.BASE_DIR, 'geojson_data')
    
    try:
        with open(os.path.join(geojson_dir, 'upazilas.geojson'), 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        upazilas = []
        for feat in data['features']:
            props = feat['properties']
            
            if district_name and props.get('district_en') != district_name:
                continue
                
            upazilas.append({
                'name_en': props.get('name_en'),
                'name_bn': props.get('name_bn', '').strip(),
                'district_en': props.get('district_en')
            })
            
        upazilas.sort(key=lambda x: x['name_en'])
        return JsonResponse({'upazilas': upazilas})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_farmers(request):
    """Get paginated list of farmers with filtering"""
    try:
        # Get query parameters
        filters = build_filters(request)
        
        # Pagination
        try:
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 50))
        except ValueError:
            page = 1
            limit = 50
            
        result = get_farmers_from_db(filters, page, limit)
        total_count = result.get('total_count', 0)
        total_pages = (total_count + limit - 1) // limit if limit > 0 else 1
        
        return JsonResponse({
            'farmers': result['farmers'],
            'total_farmers': total_count,
            'total_pages': total_pages,
            'dynamic_education': result['dynamic_education'],
            'dynamic_classes': result['dynamic_classes'],
            'page': page,
            'limit': limit
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        import traceback
        print(f"Error in get_farmers: {e}")
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

def get_filter_options(request):
    """Get distinct values for filter dropdowns"""
    try:
        options = get_distinct_options_from_db()
        return JsonResponse(options, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)

def get_area_stats(request):
    """API for area-wise farmer counts (Statistics) - Now returns English keys for reliability"""
    try:
        group_by = request.GET.get('group_by', 'Upazila')
        filters = build_filters(request)
        mapper = LocationMapper.get_instance()
        
        # Always fetch stats by Bengali names from DB
        db_group = 'District' if group_by == 'Division' else group_by
        stats_bn = get_area_stats_from_db(filters, db_group)
        
        # Translate BN stats (from DB) to EN stats (for Map) using LocationMapper
        stats_en = {}
        entity_key = 'districts' if (group_by == 'Division' or group_by == 'District') else 'upazilas'
        
        # For Division aggregation, we need GeoJSON mapping
        geojson_dir = os.path.join(settings.BASE_DIR, 'geojson_data')
        district_to_division = {}
        if group_by == 'Division':
            with open(os.path.join(geojson_dir, 'districts.geojson'), 'r', encoding='utf-8') as f:
                d_data = json.load(f)
                district_to_division = {f['properties']['name_en']: f['properties']['division_en'] for f in d_data['features']}

        for bn_db_name, count in stats_bn.items():
            en_name = mapper.get_en_name(entity_key, bn_db_name)
            if en_name:
                if group_by == 'Division':
                    div_en = district_to_division.get(en_name)
                    if div_en:
                        stats_en[div_en] = stats_en.get(div_en, 0) + count
                else:
                    stats_en[en_name] = stats_en.get(en_name, 0) + count
        
        return JsonResponse(stats_en, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        print(f"Error in get_area_stats: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

def get_field_forces(request):
    """Get field forces filtered by location"""
    try:
        # Get filters
        division_filter = request.GET.get('division')
        district_filter = request.GET.get('district')
        upazila_filter = request.GET.get('upazila')
        business_filter = request.GET.get('business', 'F')
        
        # Fetch field forces for the requested business
        all_forces = get_field_forces_from_db(business_filter)
        
        # Load mapping data for filtering
        geojson_dir = os.path.join(settings.BASE_DIR, 'geojson_data')
        
        filtered_forces = []
        
        # Load Upazila/District data
        with open(os.path.join(geojson_dir, 'upazilas.geojson'), 'r', encoding='utf-8') as f:
            upazilas_data = json.load(f)
            
        with open(os.path.join(geojson_dir, 'districts.geojson'), 'r', encoding='utf-8') as f:
            districts_data = json.load(f)

        # Helper to find if a Base string matches a target string (Fuzzy)
        def is_match(base, target):
            if base is None or target is None: return False
            return is_fuzzy_match(str(base), str(target))

        # Helper to find if a Base is an Upazila in a District
        def is_upazila_in_district(base, district_en):
            for feat in upazilas_data['features']:
                props = feat['properties']
                if is_match(props.get('name_en'), base) and is_match(props.get('district_en'), district_en):
                    return True
            return False

        # Helper to find if a Base is a District in a Division
        def is_district_in_division(base, division_en):
            for feat in districts_data['features']:
                props = feat['properties']
                if is_match(props.get('name_en'), base) and is_match(props.get('division_en'), division_en):
                    return True
            return False
            
        # Helper to find if a Base is an Upazila in a Division
        def is_upazila_in_division(base, division_en):
            for feat in upazilas_data['features']:
                props = feat['properties']
                if is_match(props.get('name_en'), base) and is_match(props.get('division_en'), division_en):
                    return True
            return False

        for force in all_forces:
            base = force['base']
            if not base: continue
            
            include = False
            
            # Filter Logic
            if upazila_filter:
                # Handle Duplicate Upazila Names: Disambiguate using parent context (District/Division)
                target_upazila_feat = None
                for feat in upazilas_data['features']:
                    props = feat['properties']
                    if is_match(props.get('name_en'), upazila_filter):
                        match_context = True
                        if district_filter and not is_match(props.get('district_en'), district_filter):
                            match_context = False
                        if division_filter and not is_match(props.get('division_en'), division_filter):
                            match_context = False
                        
                        if match_context:
                            target_upazila_feat = feat
                            break
                
                if target_upazila_feat:
                    props = target_upazila_feat['properties']
                    # Match if base is the upazila itself or its parent district
                    if is_match(base, upazila_filter):
                        include = True
                    elif is_match(base, props.get('district_en')):
                        include = True
                else:
                    # Fallback to simple matching if context not found
                    if is_match(base, upazila_filter):
                        include = True

            elif district_filter:
                if is_match(base, district_filter):
                    include = True
                elif is_upazila_in_district(base, district_filter):
                    include = True
                    
            elif division_filter:
                if is_district_in_division(base, division_filter):
                    include = True
                elif is_upazila_in_division(base, division_filter):
                    include = True
            else:
                include = True
                
            if include:
                filtered_forces.append(force)
        
        return JsonResponse({'field_forces': filtered_forces}, json_dumps_params={'ensure_ascii': False})
        
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)

@require_http_methods(["GET"])
def get_population_cover_api(request):
    """API for Population Cover Bar Chart"""
    division_en = request.GET.get('division')
    district_en = request.GET.get('district')
    upazila_en = request.GET.get('upazila')
    
    filters = build_filters(request)
    data = get_population_cover_data(
        filters, 
        division_en=division_en, 
        district_en=district_en, 
        upazila_en=upazila_en
    )
    return JsonResponse({'data': data})
@require_http_methods(["GET"])
def get_gender_stats_api(request):
    """API for Gender Distribution Donut Chart"""
    filters = build_filters(request)
    data = get_gender_stats_from_db(filters)
    return JsonResponse({'data': data})

@require_http_methods(["GET"])
def get_land_stats_api(request):
    """API for Land Distribution Donut Chart"""
    filters = build_filters(request)
    data = get_land_stats_from_db(filters)
    return JsonResponse({'data': data})

@require_http_methods(["GET"])
def get_class_stats_api(request):
    """API for Farmer Class Distribution Chart"""
    filters = build_filters(request)
    data = get_class_stats_from_db(filters)
    return JsonResponse({'data': data})


@require_http_methods(["GET"])
def get_land_amount_bins_api(request):
    """API for land amount bins chart"""
    filters = build_filters(request)
    data = get_land_amount_bins_from_db(filters)
    return JsonResponse({'data': data})

@require_http_methods(["GET"])
def get_common_stats_api(request):
    """API for Common Stats (Education, Bool Stats)"""
    filters = build_filters(request)
    data = get_common_stats_from_db(filters)
    return JsonResponse({'data': data})
