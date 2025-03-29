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
]