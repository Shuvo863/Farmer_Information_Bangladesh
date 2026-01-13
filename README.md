# Bangladesh Map Project

This Django project displays an interactive map of Bangladesh with administrative boundaries (divisions, districts, and upazilas) with Bangla translations.

## Features

- Interactive map showing Bangladesh administrative boundaries
- Three-level filtering: Division → District → Upazila
- All names translated to Bangla (বাংলা)
- Dynamic zoom and filtering based on selections
- Labels showing names on each polygon
- Transparent colored boundaries for different administrative levels

## Setup Instructions

1. **Activate the virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Process the shapefile (if not already done):**
   ```bash
   python process_shapefile.py
   ```
   This will:
   - Convert the shapefile to GeoJSON
   - Create district and division GeoJSON files
   - Translate all names to Bangla

3. **Run migrations (if needed):**
   ```bash
   python manage.py migrate
   ```

4. **Start the development server:**
   ```bash
   python manage.py runserver
   ```

5. **Access the application:**
   Open your browser and go to: `http://127.0.0.1:8000/`

## Project Structure

```
.
├── bangladesh_map/          # Django project settings
├── mapapp/                  # Main Django app
│   ├── templates/          # HTML templates
│   ├── static/             # Static files (CSS, JS)
│   └── views.py            # View functions
├── geojson_data/           # Generated GeoJSON files
│   ├── divisions.geojson
│   ├── districts.geojson
│   └── upazilas.geojson
├── upazila_shapefile/      # Original shapefile
├── process_shapefile.py    # Script to process shapefile
├── requirements.txt        # Python dependencies
└── venv/                   # Virtual environment
```

## Usage

1. **Initial View:** On page load, all divisions of Bangladesh are shown with different transparent colors.

2. **Select Division:** Choose a division from the dropdown to:
   - Zoom to that division
   - Show only districts within that division
   - Enable the district dropdown

3. **Select District:** Choose a district to:
   - Zoom to that district
   - Show only upazilas within that district
   - Enable the upazila dropdown

4. **Select Upazila:** Choose an upazila to:
   - Highlight the selected upazila in red
   - Show all upazilas in the same district
   - Keep the selected upazila highlighted

## API Endpoints

- `/api/divisions/` - Get list of all divisions
- `/api/districts/?division=<name>` - Get districts (optionally filtered by division)
- `/api/upazilas/?district=<name>` - Get upazilas (optionally filtered by district)
- `/api/geojson/<layer_type>/` - Get GeoJSON data (divisions, districts, or upazilas)

## Technologies Used

- Django 4.2.7
- Leaflet.js for map visualization
- GeoPandas for shapefile processing
- Google Translate API for Bangla translations

## Notes

- The map shows only Bangladesh boundaries (no world map background)
- All administrative names are displayed in Bangla
- Colors are automatically assigned to different administrative units
- Labels are positioned at the centroid of each polygon

