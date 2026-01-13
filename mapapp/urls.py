from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('analytics/', views.analytics, name='analytics'),
    path('api/geojson/<str:layer_type>/', views.get_geojson, name='get_geojson'),
    path('api/divisions/', views.get_divisions, name='get_divisions'),
    path('api/districts/', views.get_districts, name='get_districts'),
    path('api/upazilas/', views.get_upazilas, name='get_upazilas'),
    path('api/farmers/', views.get_farmers, name='get_farmers'),
    path('api/filter-options/', views.get_filter_options, name='get_filter_options'),
    path('api/field-forces/', views.get_field_forces, name='get_field_forces'),
    path('api/area-stats/', views.get_area_stats, name='get_area_stats'),
    path('api/population-cover/', views.get_population_cover_api, name='get_population_cover_api'),
    path('api/gender-stats/', views.get_gender_stats_api, name='gender_stats_api'),
    path('api/land-stats/', views.get_land_stats_api, name='land_stats_api'),
    path('api/class-stats/', views.get_class_stats_api, name='class_stats_api'),
    path('api/common-stats/', views.get_common_stats_api, name='common_stats_api'),
    path('api/land-amount-bins/', views.get_land_amount_bins_api, name='land_amount_bins_api'),
]

