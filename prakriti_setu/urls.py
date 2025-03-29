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
]