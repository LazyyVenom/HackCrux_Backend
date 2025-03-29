from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('login/', views.admin_login, name='admin_login'),
    path('register/', views.admin_register, name='admin_register'),
    path('logout/', views.admin_logout, name='admin_logout'),
    path('profile/', views.admin_profile, name='admin_profile'),
    
    # Event management endpoints
    path('events/', views.get_events, name='get_events'),
    path('events/add/', views.add_event, name='add_event'),
    path('events/<int:pk>/update/', views.update_event, name='update_event'),
    path('events/<int:pk>/status/', views.update_event_status, name='update_event_status'),
    path('events/<int:pk>/delete/', views.delete_event, name='delete_event'),
    path('events/<int:pk>/registrations/', views.get_event_registrations, name='get_event_registrations'),
    
    # Donation management endpoints
    path('donations/initialize/', views.initialize_donation_fields, name='initialize_donation_fields'),
    path('donations/', views.get_donations, name='get_donations'),
    path('donations/fields/', views.get_donation_fields, name='get_donation_fields'),
    path('donations/<int:pk>/status/', views.update_donation_status, name='update_donation_status'),
    
    # SOS management endpoints
    path('sos/all/', views.admin_get_all_sos_alerts, name='admin_get_all_sos_alerts'),
    path('sos/by-city/', views.admin_get_sos_alerts_by_city, name='admin_get_sos_alerts_by_city'),
    path('sos/city/<str:city>/', views.admin_get_sos_alerts_by_city_name, name='admin_get_sos_alerts_by_city_name'),
    path('sos/<int:alert_id>/status/', views.admin_update_sos_alert_status, name='admin_update_sos_alert_status'),
    path('sos/<str:city>/status/', views.admin_update_sos_alert_status_by_city, name='admin_update_sos_alert_status_by_city'),
    path('sos/statistics/', views.admin_get_sos_statistics, name='admin_get_sos_statistics'),
    
    # Resource capacity management endpoints
    path('resources/', views.get_resources, name='get_resources'),
    path('resources/type/<str:resource_type>/', views.get_resources_by_type, name='get_resources_by_type'),
    path('resources/location/', views.get_resources_by_location, name='get_resources_by_location'),
    path('resources/add/', views.add_resource, name='add_resource'),
    path('resources/<int:pk>/update/', views.update_resource, name='update_resource'),
    path('resources/<int:pk>/delete/', views.delete_resource, name='delete_resource'),
]