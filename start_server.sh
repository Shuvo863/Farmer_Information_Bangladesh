#!/bin/bash
# Startup script for Bangladesh Map Project

echo "Activating virtual environment..."
source venv/bin/activate

echo "Checking if GeoJSON files exist..."
if [ ! -f "geojson_data/divisions.geojson" ] || [ ! -f "geojson_data/districts.geojson" ] || [ ! -f "geojson_data/upazilas.geojson" ]; then
    echo "GeoJSON files not found. Processing shapefile..."
    python process_shapefile.py
fi

echo "Starting Django development server..."
python manage.py runserver 0.0.0.0:8000

