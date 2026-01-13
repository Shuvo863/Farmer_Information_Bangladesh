#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput || true

echo "Starting Django server on 0.0.0.0:8113..."
exec python manage.py runserver 0.0.0.0:8113

