import urllib
from sqlalchemy import create_engine, text
import pandas as pd
import os
from django.conf import settings

# Database Configuration (Derived from transfer_data.py)
SERVER = '192.168.100.129'
DATABASE = 'AIDataset'
USERNAME = 'sa'
PASSWORD = 'dataport'
DRIVER = 'ODBC Driver 17 for SQL Server'
TABLE_NAME = 'farmer_information'
SCHEMA_NAME = 'dbo'
import time

# Simple cache for dynamic filters
_filter_cache = {
    'last_update': 0,
    'education': [],
    'classes': [],
    'ttl': 300 # 5 minutes
}

# Field Force Database Configuration
FF_SERVER = '192.168.100.26'
FF_DATABASE = 'GroupExpense'
FF_USERNAME = 'sa'
FF_PASSWORD = 'dataport'
FF_TABLE_NAME = 'Level1'

# Reverse Mapping (English SQL Column to Bengali JSON Key)
REVERSE_COLUMN_MAPPING = {
    "IMG": "IMG",
    "Class": "Class",
    "FarmerName": "কৃষকের নাম",
    "FatherName": "পিতার নাম",
    "MotherName": "মাতার নাম",
    "SpouseName": "স্বামী/স্ত্রীর নাম",
    "Gender": "কৃষকের জেন্ডার",
    "VillageName": "গ্রামের নাম",
    "ParaName": "পাড়ার নাম",
    "BlockName": "ব্লকের নাম",
    "UnionPourashava": "ইউনিয়ন/পৌরসভা",
    "Upazila": "উপজেলা",
    "District": "জেলা",
    "FarmerIdNo": "কৃষক পরিচিতি নং",
    "FarmerCardNo": "কৃষক সহায়তা কার্ড নং",
    "FarmerFamilyNo": "কৃষক পরিবার নম্বর",
    "MobileNo": "মোবাইল নম্বর",
    "NID": "জাতীয় পরিচয়পত্র নং",
    "DOB": "জন্ম তারিখ",
    "Education": "শিক্ষাগত যোগ্যতা",
    "SmartPhoneUser": "স্মার্ট ফোন ব্যবহারকারী",
    "OrganizationName": "কৃষক সংগঠনের নাম",
    "TrainingReceived": "প্রাপ্ত প্রশিক্ষণ",
    "OtherIncomeSource": "কৃষি ব্যতিত আয়ের অন্য উৎস",
    "TotalLand": "মোট জমি",
    "OwnLand": "নিজ জমি",
    "LeaseLand": "লিজ জমি",
    "BorgaLand": "বর্গা জমি",
    "Crop1": "ফসল-১",
    "Crop2": "ফসল-২",
    "Crop3": "ফসল-৩",
    "Crop4": "ফসল-৪"
}

# Singleton Engine for Connection Pooling
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        # Add a connection timeout to reduce long-hanging TCP attempts
        connection_params = urllib.parse.quote_plus(
            f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};Connection Timeout=60"
        )
        connection_string = f"mssql+pyodbc:///?odbc_connect={connection_params}"
        _engine = create_engine(
            connection_string,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            pool_pre_ping=True
        )
    return _engine

import concurrent.futures

def get_farmers_from_db(filters=None, page=1, limit=50):
    engine = get_engine()
    
    # Base Query
    base_query = f"FROM {SCHEMA_NAME}.[{TABLE_NAME}]"
    where_clauses = []
    params = {}
    
    is_filtered = False

    if filters:
        if 'district_list' in filters:
            districts = filters['district_list']
            if districts:
                placeholders = ", ".join([f":d{i}" for i in range(len(districts))])
                where_clauses.append(f"District IN ({placeholders})")
                for i, d in enumerate(districts):
                    params[f"d{i}"] = d
                is_filtered = True
            else:
                where_clauses.append("1=0") 
                is_filtered = True
            
        if 'district_bn' in filters:
            where_clauses.append("District = :district_bn")
            params['district_bn'] = filters['district_bn']
            is_filtered = True
            
        if 'upazila_list' in filters:
            upazilas = filters['upazila_list']
            if upazilas:
                u_placeholders = ", ".join([f":u{i}" for i in range(len(upazilas))])
                where_clauses.append(f"Upazila IN ({u_placeholders})")
                for i, u in enumerate(upazilas):
                    params[f"u{i}"] = u
                is_filtered = True
            else:
                where_clauses.append("1=0")
                is_filtered = True
        elif 'upazila_bn' in filters:
            where_clauses.append("Upazila = :upazila_bn")
            params['upazila_bn'] = filters['upazila_bn']
            is_filtered = True
            
        if filters.get('class'):
            where_clauses.append("Class = :class")
            params['class'] = filters['class']
            is_filtered = True
            
        if filters.get('gender'):
            where_clauses.append("Gender = :gender")
            params['gender'] = filters['gender']
            is_filtered = True
            
        if filters.get('education'):
            where_clauses.append("Education = :education")
            params['education'] = filters['education']
            is_filtered = True
            
        if filters.get('smart_phone'):
            where_clauses.append("SmartPhoneUser = :smart_phone")
            params['smart_phone'] = filters['smart_phone']
            is_filtered = True
            
        if filters.get('search'):
            search_pattern = f"%{filters['search']}%"
            where_clauses.append("(FarmerName LIKE :search OR Upazila LIKE :search OR District LIKE :search OR VillageName LIKE :search OR FarmerIdNo LIKE :search)")
            params['search'] = search_pattern
            is_filtered = True

        if filters.get('land_amount') is not None and filters.get('land_operator'):
            try:
                # User sends numeric string from frontend
                land_val = float(filters['land_amount'])
                operator = filters['land_operator']
                
                if operator == 'greater':
                    where_clauses.append("TotalLandNumeric > :land_val")
                elif operator == 'equal':
                    where_clauses.append("TotalLandNumeric = :land_val")
                elif operator == 'less':
                    where_clauses.append("TotalLandNumeric < :land_val")
                    
                params['land_val'] = land_val
                is_filtered = True
            except (ValueError, TypeError):
                pass
    
    where_stmt = " WHERE " + " AND ".join(where_clauses) if where_clauses else " WHERE 1=1 "
    
    # Count Query construction
    count_query_sql = text(f"SELECT COUNT(*) {base_query} {where_stmt}")
    
    # Data Query construction
    offset = (page - 1) * limit
    data_query_sql = text(f"""
        SELECT *
        {base_query} 
        {where_stmt}
        ORDER BY FarmerIdNo
        OFFSET {offset} ROWS
        FETCH NEXT {limit} ROWS ONLY
    """)
    
    # Helper functions for parallel execution
    def fetch_count(conn):
        # Cache Strategy for Unfiltered Count
        if not is_filtered:
            # Check cache
            cached_count = _filter_cache.get('total_count')
            if cached_count and (time.time() - _filter_cache['last_update'] < _filter_cache['ttl']):
                return cached_count
        
        # Explicitly open a new connection for thread safety if engine is shared, 
        # but SQLAlchemy engine is thread-safe. We need a connection per thread usually.
        # However, passing 'conn' from outside might not work if we want true parallel DB calls 
        # because the underlying DBAPI connection might block.
        # Best practice: Creating a fresh connection from the engine pool in each thread.
        with engine.connect() as t_conn:
            cnt = t_conn.execute(count_query_sql, params).scalar()
            
        if not is_filtered:
            _filter_cache['total_count'] = cnt
        return cnt

    def fetch_data():
        with engine.connect() as t_conn:
            df = pd.read_sql(data_query_sql, t_conn, params=params)
             # Map columns back to Bengali
            df.rename(columns=REVERSE_COLUMN_MAPPING, inplace=True)
            # Replace NaN with None for JSON compatibility
            df = df.astype(object).where(pd.notnull(df), None)
            return df

    def fetch_options():
        # Check if update needed
        now = time.time()
        if now - _filter_cache['last_update'] > _filter_cache['ttl'] or not _filter_cache['education']:
             with engine.connect() as t_conn:
                education_query = text(f"SELECT DISTINCT Education {base_query} WHERE Education IS NOT NULL AND Education != ''")
                class_query = text(f"SELECT DISTINCT Class {base_query} WHERE Class IS NOT NULL AND Class != ''")
                
                edu = sorted([row[0] for row in t_conn.execute(education_query)])
                cls = sorted([row[0] for row in t_conn.execute(class_query)])
                
                _filter_cache['education'] = edu
                _filter_cache['classes'] = cls
                _filter_cache['last_update'] = now
                return edu, cls
        else:
            return _filter_cache['education'], _filter_cache['classes']

    try:
        # Use ThreadPoolExecutor for parallel DB operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submit tasks
            # Note: We don't pass 'conn' to threads, we let them create their own from pool
            future_count = executor.submit(fetch_count, None)
            future_data = executor.submit(fetch_data)
            future_options = executor.submit(fetch_options)
            
            # Wait for results
            total_count = future_count.result()
            df = future_data.result()
            dynamic_education, dynamic_classes = future_options.result()
            
            return {
                'farmers': df.to_dict(orient='records'),
                'total_count': total_count,
                'dynamic_education': dynamic_education,
                'dynamic_classes': dynamic_classes
            }
            
    except Exception as e:
        print(f"DB Error: {e}")
        import traceback
        traceback.print_exc()
        return {'farmers': [], 'total_count': 0, 'dynamic_education': [], 'dynamic_classes': []}

def get_area_stats_from_db(filters=None, group_by='Upazila'):
    """Get farmer counts grouped by Division, District, or Upazila"""
    engine = get_engine()
    
    # Base Query
    base_query = f"FROM {SCHEMA_NAME}.[{TABLE_NAME}]"
    where_clauses = []
    params = {}
    
    # Apply standard filters (except the one we are grouping by, usually)
    # But actually, the user wants counts based on CURRENT filters.
    if filters:
        if filters.get('district_list'):
            districts = filters['district_list']
            placeholders = ", ".join([f":d{i}" for i in range(len(districts))])
            where_clauses.append(f"District IN ({placeholders})")
            for i, d in enumerate(districts):
                params[f"d{i}"] = d
        
        if filters.get('district_bn'):
            where_clauses.append("District = :district_bn")
            params['district_bn'] = filters['district_bn']
            
        if filters.get('upazila_list'):
            upazilas = filters['upazila_list']
            if upazilas:
                u_placeholders = ", ".join([f":u{i}" for i in range(len(upazilas))])
                where_clauses.append(f"Upazila IN ({u_placeholders})")
                for i, u in enumerate(upazilas):
                    params[f"u{i}"] = u
        elif filters.get('upazila_bn'):
            where_clauses.append("Upazila = :upazila_bn")
            params['upazila_bn'] = filters['upazila_bn']
            
        if filters.get('class'):
            where_clauses.append("Class = :class")
            params['class'] = filters['class']
            
        if filters.get('gender'):
            where_clauses.append("Gender = :gender")
            params['gender'] = filters['gender']
            
        if filters.get('education'):
            where_clauses.append("Education = :education")
            params['education'] = filters['education']
            
        if filters.get('smart_phone'):
            where_clauses.append("SmartPhoneUser = :smart_phone")
            params['smart_phone'] = filters['smart_phone']

        if filters.get('search'):
            search_pattern = f"%{filters['search']}%"
            where_clauses.append("(FarmerName LIKE :search OR Upazila LIKE :search OR District LIKE :search OR VillageName LIKE :search OR FarmerIdNo LIKE :search)")
            params['search'] = search_pattern

        if filters.get('land_amount') is not None and filters.get('land_operator'):
            try:
                land_val = float(filters['land_amount'])
                operator = filters['land_operator']
                if operator == 'greater': where_clauses.append("TotalLandNumeric > :land_val")
                elif operator == 'equal': where_clauses.append("TotalLandNumeric = :land_val")
                elif operator == 'less': where_clauses.append("TotalLandNumeric < :land_val")
                params['land_val'] = land_val
            except: pass

    where_stmt = " WHERE " + " AND ".join(where_clauses) if where_clauses else " WHERE 1=1 "
    
    # Ensure group_by is safe 
    allowed_groups = {'District', 'Upazila'}
    if group_by not in allowed_groups: group_by = 'Upazila'
    
    # Use exact column names as data is sanitized
    group_col = group_by
    
    query = text(f"""
        SELECT {group_col} as Area, COUNT(*) as Count 
        {base_query} 
        {where_stmt}
        GROUP BY {group_col}
    """)
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)
            return df.set_index('Area')['Count'].to_dict()
    except Exception as e:
        print(f"Stats Error: {e}")
        return {}

def get_gender_stats_from_db(filters=None):
    """Get gender counts: Male, Female, and No Information"""
    engine = get_engine()
    
    # Base Query
    base_query = f"FROM {SCHEMA_NAME}.[{TABLE_NAME}]"
    where_clauses = []
    params = {}
    
    # Apply standard filters
    if filters:
        if filters.get('district_list'):
            districts = filters['district_list']
            placeholders = ", ".join([f":d{i}" for i in range(len(districts))])
            where_clauses.append(f"District IN ({placeholders})")
            for i, d in enumerate(districts):
                params[f"d{i}"] = d
        
        if filters.get('district_bn'):
            where_clauses.append("District = :district_bn")
            params['district_bn'] = filters['district_bn']
            
        if filters.get('upazila_list'):
            upazilas = filters['upazila_list']
            if upazilas:
                u_placeholders = ", ".join([f":u{i}" for i in range(len(upazilas))])
                where_clauses.append(f"Upazila IN ({u_placeholders})")
                for i, u in enumerate(upazilas):
                    params[f"u{i}"] = u
        elif filters.get('upazila_bn'):
            where_clauses.append("Upazila = :upazila_bn")
            params['upazila_bn'] = filters['upazila_bn']
            
        if filters.get('class'):
            where_clauses.append("Class = :class")
            params['class'] = filters['class']
            
        if filters.get('education'):
            where_clauses.append("Education = :education")
            params['education'] = filters['education']
            
        if filters.get('smart_phone'):
            where_clauses.append("SmartPhoneUser = :smart_phone")
            params['smart_phone'] = filters['smart_phone']

        if filters.get('search'):
            search_pattern = f"%{filters['search']}%"
            where_clauses.append("(FarmerName LIKE :search OR Upazila LIKE :search OR District LIKE :search OR VillageName LIKE :search OR FarmerIdNo LIKE :search)")
            params['search'] = search_pattern

        if filters.get('land_amount') is not None and filters.get('land_operator'):
            try:
                land_val = float(filters['land_amount'])
                operator = filters['land_operator']
                if operator == 'greater': where_clauses.append("TotalLandNumeric > :land_val")
                elif operator == 'equal': where_clauses.append("TotalLandNumeric = :land_val")
                elif operator == 'less': where_clauses.append("TotalLandNumeric < :land_val")
                params['land_val'] = land_val
            except: pass

    where_stmt = " WHERE " + " AND ".join(where_clauses) if where_clauses else " WHERE 1=1 "
    
    query = text(f"""
        SELECT 
            CASE 
                WHEN Gender IS NULL OR Gender = '' THEN 'No Information'
                WHEN Gender = N'পুরুষ' THEN 'Male'
                WHEN Gender = N'মহিলা' THEN 'Female'
                ELSE Gender 
            END as Category,
            COUNT(*) as Count 
        {base_query} 
        {where_stmt}
        GROUP BY 
            CASE 
                WHEN Gender IS NULL OR Gender = '' THEN 'No Information'
                WHEN Gender = N'পুরুষ' THEN 'Male'
                WHEN Gender = N'মহিলা' THEN 'Female'
                ELSE Gender 
            END
    """)
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)
            return df.set_index('Category')['Count'].to_dict()
    except Exception as e:
        print(f"Gender Stats Error: {e}")
        return {}

def get_land_stats_from_db(filters=None):
    """Get total land counts: Own, Lease, Borga"""
    engine = get_engine()
    
    # Base Query
    base_query = f"FROM {SCHEMA_NAME}.[{TABLE_NAME}]"
    where_clauses = []
    params = {}
    
    # Apply standard filters
    if filters:
        if filters.get('district_list'):
            districts = filters['district_list']
            placeholders = ", ".join([f":d{i}" for i in range(len(districts))])
            where_clauses.append(f"District IN ({placeholders})")
            for i, d in enumerate(districts):
                params[f"d{i}"] = d
        
        if filters.get('district_bn'):
            where_clauses.append("District = :district_bn")
            params['district_bn'] = filters['district_bn']
            
        if filters.get('upazila_list'):
            upazilas = filters['upazila_list']
            if upazilas:
                u_placeholders = ", ".join([f":u{i}" for i in range(len(upazilas))])
                where_clauses.append(f"Upazila IN ({u_placeholders})")
                for i, u in enumerate(upazilas):
                    params[f"u{i}"] = u
        elif filters.get('upazila_bn'):
            where_clauses.append("Upazila = :upazila_bn")
            params['upazila_bn'] = filters['upazila_bn']
            
        if filters.get('class'):
            where_clauses.append("Class = :class")
            params['class'] = filters['class']
            
        if filters.get('education'):
            where_clauses.append("Education = :education")
            params['education'] = filters['education']
            
        if filters.get('smart_phone'):
            where_clauses.append("SmartPhoneUser = :smart_phone")
            params['smart_phone'] = filters['smart_phone']

        if filters.get('search'):
            search_pattern = f"%{filters['search']}%"
            where_clauses.append("(FarmerName LIKE :search OR Upazila LIKE :search OR District LIKE :search OR VillageName LIKE :search OR FarmerIdNo LIKE :search)")
            params['search'] = search_pattern

        if filters.get('land_amount') is not None and filters.get('land_operator'):
            try:
                land_val = float(filters['land_amount'])
                operator = filters['land_operator']
                if operator == 'greater': where_clauses.append("TotalLandNumeric > :land_val")
                elif operator == 'equal': where_clauses.append("TotalLandNumeric = :land_val")
                elif operator == 'less': where_clauses.append("TotalLandNumeric < :land_val")
                params['land_val'] = land_val
            except: pass

    where_stmt = " WHERE " + " AND ".join(where_clauses) if where_clauses else " WHERE 1=1 "
    
    # Logic to convert Bengali numbers to English and cast to FLOAT
    # Assumes format "N শতক" or similar. We translate digits and remove " শতক".
    def land_sum_query(col_name):
        return f"SUM(TRY_CAST(REPLACE(TRANSLATE({col_name}, N'০১২৩৪৫৬৭৮৯', '0123456789'), N' শতক', '') as FLOAT))"

    query = text(f"""
        SELECT 
            {land_sum_query('OwnLand')} as TotalOwnLand,
            {land_sum_query('LeaseLand')} as TotalLeaseLand,
            {land_sum_query('BorgaLand')} as TotalBorgaLand
        {base_query} 
        {where_stmt}
    """)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(query, params).fetchone()
            if result:
                 return {
                    'Own Land': result[0] or 0,
                    'Lease Land': result[1] or 0,
                    'Borga Land': result[2] or 0
                }
            return {'Own Land': 0, 'Lease Land': 0, 'Borga Land': 0}
            
    except Exception as e:
        print(f"Land Stats Error: {e}")
        return {'Own Land': 0, 'Lease Land': 0, 'Borga Land': 0}

def get_class_stats_from_db(filters=None):
    """Get counts grouped by Farmer Class"""
    engine = get_engine()
    
    # Base Query
    base_query = f"FROM {SCHEMA_NAME}.[{TABLE_NAME}]"
    where_clauses = []
    params = {}
    
    # Apply standard filters
    if filters:
        if filters.get('district_list'):
            districts = filters['district_list']
            placeholders = ", ".join([f":d{i}" for i in range(len(districts))])
            where_clauses.append(f"District IN ({placeholders})")
            for i, d in enumerate(districts):
                params[f"d{i}"] = d
        
        if filters.get('district_bn'):
            where_clauses.append("District = :district_bn")
            params['district_bn'] = filters['district_bn']
            
        if filters.get('upazila_list'):
            upazilas = filters['upazila_list']
            if upazilas:
                u_placeholders = ", ".join([f":u{i}" for i in range(len(upazilas))])
                where_clauses.append(f"Upazila IN ({u_placeholders})")
                for i, u in enumerate(upazilas):
                    params[f"u{i}"] = u
        elif filters.get('upazila_bn'):
            where_clauses.append("Upazila = :upazila_bn")
            params['upazila_bn'] = filters['upazila_bn']
            
        if filters.get('class'):
            where_clauses.append("Class = :class")
            params['class'] = filters['class']
            
        if filters.get('education'):
            where_clauses.append("Education = :education")
            params['education'] = filters['education']
            
        if filters.get('smart_phone'):
            where_clauses.append("SmartPhoneUser = :smart_phone")
            params['smart_phone'] = filters['smart_phone']

        if filters.get('search'):
            search_pattern = f"%{filters['search']}%"
            where_clauses.append("(FarmerName LIKE :search OR Upazila LIKE :search OR District LIKE :search OR VillageName LIKE :search OR FarmerIdNo LIKE :search)")
            params['search'] = search_pattern

        if filters.get('land_amount') is not None and filters.get('land_operator'):
            try:
                land_val = float(filters['land_amount'])
                operator = filters['land_operator']
                if operator == 'greater': where_clauses.append("TotalLandNumeric > :land_val")
                elif operator == 'equal': where_clauses.append("TotalLandNumeric = :land_val")
                elif operator == 'less': where_clauses.append("TotalLandNumeric < :land_val")
                params['land_val'] = land_val
            except: pass

    where_stmt = " WHERE " + " AND ".join(where_clauses) if where_clauses else " WHERE 1=1 "
    
    # We strip 'শ্রেণী: ' prefix for cleaner labels
    # Using SQL REPLACE for efficiency if possible, or python processing
    query = text(f"""
        SELECT Class, COUNT(*) as Count 
        {base_query} 
        {where_stmt}
        GROUP BY Class
    """)
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)
            # Python side processing to clean keys
            cleaned_data = {}
            for index, row in df.iterrows():
                key = row['Class']
                if key:
                    # Remove prefix if present
                    clean_key = key.replace('শ্রেণী: ', '').strip()
                    cleaned_data[clean_key] = row['Count']
            return cleaned_data
    except Exception as e:
        print(f"Class Stats Error: {e}")
        return {}
    except Exception as e:
        print(f"Class Stats Error: {e}")
        return {}

def get_land_amount_bins_from_db(filters=None):
    """Return counts of farmers by TotalLandNumeric bins.
    Bins: 0-10, 10-50, 50-100, 100-200, 200-300, 300-500, >500 (but <100000), others (>=100000)
    """
    engine = get_engine()
    base_query = f"FROM {SCHEMA_NAME}.[{TABLE_NAME}]"
    where_clauses = []
    params = {}

    # Apply same filter logic as other functions
    if filters:
        if filters.get('district_list'):
            districts = filters['district_list']
            placeholders = ", ".join([f":d{i}" for i in range(len(districts))])
            where_clauses.append(f"District IN ({placeholders})")
            for i, d in enumerate(districts): params[f"d{i}"] = d
        if filters.get('district_bn'):
            where_clauses.append("District = :district_bn")
            params['district_bn'] = filters['district_bn']
        if filters.get('upazila_list'):
            upazilas = filters['upazila_list']
            if upazilas:
                u_placeholders = ", ".join([f":u{i}" for i in range(len(upazilas))])
                where_clauses.append(f"Upazila IN ({u_placeholders})")
                for i, u in enumerate(upazilas): params[f"u{i}"] = u
        elif filters.get('upazila_bn'):
            where_clauses.append("Upazila = :upazila_bn")
            params['upazila_bn'] = filters['upazila_bn']
        if filters.get('class'):
            where_clauses.append("Class = :class")
            params['class'] = filters['class']
        if filters.get('education'):
            where_clauses.append("Education = :education")
            params['education'] = filters['education']
        if filters.get('smart_phone'):
            where_clauses.append("SmartPhoneUser = :smart_phone")
            params['smart_phone'] = filters['smart_phone']
        if filters.get('search'):
            search_pattern = f"%{filters['search']}%"
            where_clauses.append("(FarmerName LIKE :search OR Upazila LIKE :search OR District LIKE :search OR VillageName LIKE :search OR FarmerIdNo LIKE :search)")
            params['search'] = search_pattern

    where_stmt = " WHERE " + " AND ".join(where_clauses) if where_clauses else " WHERE 1=1 "

    # Build query with CASE counts for each bin
    # Parse TotalLand which may be stored as Bangla digits with unit like '১২৩ শতক'.
    # Convert Bangla digits to ASCII digits and remove ' শতক' then TRY_CAST to FLOAT.
    # Compute the parsed numeric TotalLand once per row using CROSS APPLY to avoid repeating the expression
    parsed_totalland = "TRY_CAST(REPLACE(TRANSLATE(TotalLand, N'০১২৩৪৫৬৭৮৯', '0123456789'), N' শতক', '') as FLOAT)"

    # Use CROSS APPLY to expose parsed value as v.p then aggregate using simple CASEs
    query = text(f"""
        SELECT
            SUM(CASE WHEN v.p >= 0 AND v.p <= 10 THEN 1 ELSE 0 END) as b0_10,
            SUM(CASE WHEN v.p > 10 AND v.p <= 50 THEN 1 ELSE 0 END) as b10_50,
            SUM(CASE WHEN v.p > 50 AND v.p <= 100 THEN 1 ELSE 0 END) as b50_100,
            SUM(CASE WHEN v.p > 100 AND v.p <= 200 THEN 1 ELSE 0 END) as b100_200,
            SUM(CASE WHEN v.p > 200 AND v.p <= 300 THEN 1 ELSE 0 END) as b200_300,
            SUM(CASE WHEN v.p > 300 AND v.p <= 500 THEN 1 ELSE 0 END) as b300_500,
            SUM(CASE WHEN v.p > 500 AND v.p < 100000 THEN 1 ELSE 0 END) as b500_plus,
            SUM(CASE WHEN v.p >= 100000 THEN 1 ELSE 0 END) as others
        FROM {SCHEMA_NAME}.[{TABLE_NAME}]
        CROSS APPLY (SELECT {parsed_totalland} as p) v
        {where_stmt}
    """)

    try:
        with engine.connect() as conn:
            row = conn.execute(query, params).fetchone()
            if row:
                return {
                    '0_10': int(row[0] or 0),
                    '10_50': int(row[1] or 0),
                    '50_100': int(row[2] or 0),
                    '100_200': int(row[3] or 0),
                    '200_300': int(row[4] or 0),
                    '300_500': int(row[5] or 0),
                    '500_plus': int(row[6] or 0),
                    'others': int(row[7] or 0)
                }
            return {'0_10':0,'10_50':0,'50_100':0,'100_200':0,'200_300':0,'300_500':0,'500_plus':0,'others':0}
    except Exception as e:
        print(f"Land amount bins error: {e}")
        return {'0_10':0,'10_50':0,'50_100':0,'100_200':0,'200_300':0,'300_500':0,'500_plus':0,'others':0}

def get_common_stats_from_db(filters=None):
    """Aggregate stats for Education, NID, Mobile, Smartphone, FarmerID"""
    engine = get_engine()
    
    # Base Query construction (reuse logic)
    base_query = f"FROM {SCHEMA_NAME}.[{TABLE_NAME}]"
    where_clauses = []
    params = {}
    
    # Apply standard filters (Copy of standard filter logic)
    if filters:
        if filters.get('district_list'):
            districts = filters['district_list']
            placeholders = ", ".join([f":d{i}" for i in range(len(districts))])
            where_clauses.append(f"District IN ({placeholders})")
            for i, d in enumerate(districts): params[f"d{i}"] = d
        if filters.get('district_bn'):
            where_clauses.append("District = :district_bn")
            params['district_bn'] = filters['district_bn']
        if filters.get('upazila_list'):
            upazilas = filters['upazila_list']
            if upazilas:
                u_placeholders = ", ".join([f":u{i}" for i in range(len(upazilas))])
                where_clauses.append(f"Upazila IN ({u_placeholders})")
                for i, u in enumerate(upazilas): params[f"u{i}"] = u
        elif filters.get('upazila_bn'):
            where_clauses.append("Upazila = :upazila_bn")
            params['upazila_bn'] = filters['upazila_bn']
        if filters.get('class'):
            where_clauses.append("Class = :class")
            params['class'] = filters['class']
        if filters.get('education'):
            where_clauses.append("Education = :education")
            params['education'] = filters['education']
        if filters.get('smart_phone'):
            where_clauses.append("SmartPhoneUser = :smart_phone")
            params['smart_phone'] = filters['smart_phone']
        if filters.get('search'):
            search_pattern = f"%{filters['search']}%"
            where_clauses.append("(FarmerName LIKE :search OR Upazila LIKE :search OR District LIKE :search OR VillageName LIKE :search OR FarmerIdNo LIKE :search)")
            params['search'] = search_pattern
        if filters.get('land_amount') is not None and filters.get('land_operator'):
            try:
                land_val = float(filters['land_amount'])
                operator = filters['land_operator']
                if operator == 'greater': where_clauses.append("TotalLandNumeric > :land_val")
                elif operator == 'equal': where_clauses.append("TotalLandNumeric = :land_val")
                elif operator == 'less': where_clauses.append("TotalLandNumeric < :land_val")
                params['land_val'] = land_val
            except: pass

    where_stmt = " WHERE " + " AND ".join(where_clauses) if where_clauses else " WHERE 1=1 "

    try:
        with engine.connect() as conn:
            # 1. Education Stats
            edu_query = text(f"SELECT Education, COUNT(*) as Count {base_query} {where_stmt} GROUP BY Education")
            edu_df = pd.read_sql(edu_query, conn, params=params)
            education_data = {row['Education']: row['Count'] for index, row in edu_df.iterrows() if row['Education']}

            # 2. Boolean Stats (Consolidated Query)
            # We count non-null/non-empty values for boolean-like fields
            # For Smartphone: Explicitly count Yes and No to derive No Data
            bool_query = text(f"""
                SELECT 
                    COUNT(CASE WHEN FarmerIdNo IS NOT NULL AND FarmerIdNo != '' THEN 1 END) as HasFarmerID,
                    COUNT(CASE WHEN NID IS NOT NULL AND NID != '' THEN 1 END) as HasNID,
                    COUNT(CASE WHEN MobileNo IS NOT NULL AND MobileNo != '' THEN 1 END) as HasMobile,
                    COUNT(CASE WHEN SmartPhoneUser IN ('Yes', N'হ্যাঁ', N'√') THEN 1 END) as SmartPhone_Yes,
                    COUNT(CASE WHEN SmartPhoneUser IN ('No', N'না', N'×') THEN 1 END) as SmartPhone_No,
                    COUNT(*) as Total
                {base_query} 
                {where_stmt}
            """)
            bool_result = conn.execute(bool_query, params).fetchone()
            
            total = bool_result[5] if bool_result else 0
            
            # Smartphone logic
            sp_yes = bool_result[3] or 0
            sp_no = bool_result[4] or 0
            sp_nodata = total - (sp_yes + sp_no)

            bool_stats = {
                'farmer_id': {'Yes': bool_result[0] or 0, 'No': total - (bool_result[0] or 0)},
                'nid': {'Yes': bool_result[1] or 0, 'No': total - (bool_result[1] or 0)},
                'mobile': {'Yes': bool_result[2] or 0, 'No': total - (bool_result[2] or 0)},
                'smartphone': {'Yes': sp_yes, 'No': sp_no, 'No Data': sp_nodata}
            }

            # Expose total so frontend can show overall farmer count
            bool_stats['Total'] = total

            return {
                'education': education_data,
                'bools': bool_stats
            }

    except Exception as e:
        print(f"Common Stats Error: {e}")
        return {'education': {}, 'bools': {}}


def get_distinct_options_from_db():
    engine = get_engine()
    options = {
        'classes': [],
        'genders': [],
        'education': [],
        'smart_phone': [],
        'districts': [],
        'upazilas': []
    }
    
    queries = {
        'classes': f"SELECT DISTINCT Class FROM {SCHEMA_NAME}.[{TABLE_NAME}] WHERE Class IS NOT NULL AND Class != ''",
        'genders': f"SELECT DISTINCT Gender FROM {SCHEMA_NAME}.[{TABLE_NAME}] WHERE Gender IS NOT NULL AND Gender != ''",
        'education': f"SELECT DISTINCT Education FROM {SCHEMA_NAME}.[{TABLE_NAME}] WHERE Education IS NOT NULL AND Education != ''",
        'smart_phone': f"SELECT DISTINCT SmartPhoneUser FROM {SCHEMA_NAME}.[{TABLE_NAME}] WHERE SmartPhoneUser IS NOT NULL AND SmartPhoneUser != ''",
        'districts': f"SELECT DISTINCT District FROM {SCHEMA_NAME}.[{TABLE_NAME}] WHERE District IS NOT NULL AND District != ''",
        'upazilas': f"SELECT DISTINCT Upazila FROM {SCHEMA_NAME}.[{TABLE_NAME}] WHERE Upazila IS NOT NULL AND Upazila != ''"
    }
    
    try:
        with engine.connect() as conn:
            for key, query in queries.items():
                res = conn.execute(text(query))
                options[key] = sorted([row[0] for row in res if row[0]])
        return options
    except Exception as e:
        print(f"DB Error fetching options: {e}")
        return options

# Population Data Provider
_population_df = None
def get_population_df():
    global _population_df
    if _population_df is None:
        try:
            # Use absolute path for robustness
            file_path = os.path.join(settings.BASE_DIR, 'upazila_population.xlsx')
            _population_df = pd.read_excel(file_path)
        except Exception as e:
            print(f"Error loading population excel: {e}")
            _population_df = pd.DataFrame(columns=['Division', 'District', 'Upazila', 'Population'])
    return _population_df

def ensure_sadar_space(s):
    """Ensures there is a space before 'সদর' for consistency"""
    if not s: return s
    s = str(s).strip()
    if s.endswith('সদর') and len(s) > 3 and not s.endswith(' সদর'):
        return s[:-3] + ' সদর'
    return s

def get_population_cover_data(filters=None, division_en=None, district_en=None, upazila_en=None):
    """Aggregate population from Excel and farmer counts from DB hierarchically using Bengali names"""
    from .location_utils import LocationMapper, normalize_bn_name
    pop_df = get_population_df()
    mapper = LocationMapper.get_instance()
    
    # Determine grouping level based on filters
    group_by = 'Division'
    pop_filter_col = None
    pop_filter_val = None
    
    # We use Bengali names for grouping/filtering in the Excel too now
    if upazila_en:
        group_by = 'Upazila'
        pop_filter_col = 'Upazila'
        pop_filter_val = mapper.get_db_names('upazilas', upazila_en)[0] if mapper.get_db_names('upazilas', upazila_en) else upazila_en
    elif district_en:
        group_by = 'Upazila'
        pop_filter_col = 'District'
        pop_filter_val = mapper.get_db_names('districts', district_en)[0] if mapper.get_db_names('districts', district_en) else district_en
    elif division_en:
        group_by = 'District'
        pop_filter_col = 'Division'
        div_map = {'Khulna': 'খুলনা', 'Dhaka': 'ঢাকা', 'Chittagong': 'চট্টগ্রাম', 'Barisal': 'বরিশাল', 
                   'Rajshahi': 'রাজশাহী', 'Sylhet': 'সিলেট', 'Rangpur': 'রংপুর', 'Mymensingh': 'ময়মনসিংহ'}
        pop_filter_val = div_map.get(division_en, division_en)
    else:
        group_by = 'Division'

    # 1. Aggregate Population from Excel (NOW Bengali)
    if pop_filter_col and pop_filter_val:
        norm_val = normalize_bn_name(pop_filter_val)
        filtered_pop = pop_df[pop_df[pop_filter_col].apply(normalize_bn_name) == norm_val]
    else:
        filtered_pop = pop_df

    agg_pop = filtered_pop.groupby(group_by)['Population'].sum().to_dict()

    # 2. Aggregate Farmer Counts from DB (Bengali)
    db_group_by = 'District'
    if group_by == 'Upazila':
        db_group_by = 'Upazila'
    elif group_by == 'Division':
        db_group_by = 'District'
        
    farmer_stats_db = get_area_stats_from_db(filters, group_by=db_group_by)
    norm_farmer_stats = {normalize_bn_name(k): v for k, v in farmer_stats_db.items()}

    # 3. Merge results using normalized Bengali names
    results = []
    if group_by == 'Division':
        # Re-define div_map if not in local scope here (though it's in division_en block)
        div_map = {'Khulna': 'খুলনা', 'Dhaka': 'ঢাকা', 'Chittagong': 'চট্টগ্রাম', 'Barisal': 'বরিশাল', 
                   'Rajshahi': 'রাজশাহী', 'Sylhet': 'সিলেট', 'Rangpur': 'রংপুর', 'Mymensingh': 'ময়মনসিংহ'}
        rolled_up_farmers = {}
        for db_dist_name, count in farmer_stats_db.items():
            en_dist_name = mapper.get_en_name('districts', db_dist_name)
            if en_dist_name:
                for div_en, dists_en in mapper.division_to_districts.items():
                    if en_dist_name in dists_en:
                        div_bn = div_map.get(div_en, div_en)
                        rolled_up_farmers[div_bn] = rolled_up_farmers.get(div_bn, 0) + count
                        break
        
        for area_bn, pop_val in agg_pop.items():
            results.append({
                'area': ensure_sadar_space(area_bn),
                'population': int(pop_val),
                'farmers': int(rolled_up_farmers.get(area_bn, 0))
            })
    else:
        for area_bn, pop_val in agg_pop.items():
            norm_area = normalize_bn_name(area_bn)
            results.append({
                'area': ensure_sadar_space(area_bn),
                'population': int(pop_val),
                'farmers': int(norm_farmer_stats.get(norm_area, 0))
            })

    return results

# Field Force Engine
_ff_engine = None

def get_ff_engine():
    global _ff_engine
    if _ff_engine is None:
        connection_params = urllib.parse.quote_plus(
            f"DRIVER={{{DRIVER}}};SERVER={FF_SERVER};DATABASE={FF_DATABASE};UID={FF_USERNAME};PWD={FF_PASSWORD}"
        )
        connection_string = f"mssql+pyodbc:///?odbc_connect={connection_params}"
        _ff_engine = create_engine(
            connection_string,
            pool_size=5,
            pool_recycle=3600,
            pool_pre_ping=True
        )
    return _ff_engine

def get_field_forces_from_db(business='F'):
    engine = get_ff_engine()
    # Query: Select Level1Name and Base where Business = :business
    query = text(f"SELECT Level1Name, Base FROM dbo.{FF_TABLE_NAME} WHERE Business = :business")
    
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"business": business})
            # return list of dicts
            return [{'name': row[0], 'base': row[1]} for row in result]
    except Exception as e:
        print(f"Field Force DB Error: {e}")
        return []
