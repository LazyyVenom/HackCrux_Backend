from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('user/', views.get_user, name='get_user'),
    path('user/update/', views.update_user, name='update_user'),
    path('user/profile/', views.user_profile, name='user_profile'),
    # Event-related endpoints - fixed to match frontend API calls
    path('user/events/active/', views.get_active_events, name='active_events'),
    path('user/events/<int:event_id>/register/', views.register_for_event, name='register_for_event'),
    path('user/events/registrations/', views.get_user_registrations, name='user_registrations'),
    
    # Donation endpoints
    path('donations/fields/', views.get_donation_fields, name='donation_fields'),
    path('donations/create/', views.create_donation, name='create_donation'),
    path('donations/verify/<str:token>/', views.verify_donation, name='verify_donation'),
    path('donations/verify-details/<str:token>/', views.verify_donation_details, name='verify_donation_details'),
    path('user/donations/', views.get_user_donations, name='user_donations'),
    
    # SOS Alert endpoints
    path('sos/create/', views.create_sos_alert, name='create_sos_alert'),
    path('sos/user/', views.get_user_sos_alerts, name='get_user_sos_alerts'),
    path('sos/active/', views.get_all_active_sos_alerts, name='get_all_active_sos_alerts'),
    path('sos/<int:alert_id>/update/', views.update_sos_alert_status, name='update_sos_alert_status'),
    path('sos/by-city/', views.get_sos_alerts_by_city, name='get_sos_alerts_by_city'),
    
    # Location information endpoint
    path('location/details/', views.get_location_details, name='get_location_details'),

    # News API endpoints
    path('news/national/', views.get_national_news, name='national_news'),
    path('news/state/', views.get_state_news, name='state_news'),
    
    # New disaster news endpoints
    path('news/social/', views.get_social_disaster_news, name='social_disaster_news'),
    path('news/combined/', views.get_combined_disaster_news, name='combined_disaster_news'),
    
    # Environmental metrics endpoint
    path('location/metrics/', views.get_environmental_metrics, name='environmental_metrics'),
    
    # Admin analytics endpoint
    path('admin/analytics/', views.admin_analytics, name='admin_analytics'),
    path('disasters/', views.get_disasters, name='get_disasters'),

    # New endpoint for recent activities
    path('activities/recent/', views.get_recent_activities, name='get_recent_activities'),
    
    # New chatbot endpoint with streaming support
    path('chatbot/message/', views.chatbot_message, name='chatbot_message'),
]