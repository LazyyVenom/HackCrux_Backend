from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('user/', views.get_user, name='get_user'),
    path('user/update/', views.update_user, name='update_user'),
    # Event-related endpoints - fixed to match frontend API calls
    path('user/events/active/', views.get_active_events, name='active_events'),
    path('user/events/<int:event_id>/register/', views.register_for_event, name='register_for_event'),
    path('user/events/registrations/', views.get_user_registrations, name='user_registrations'),
]