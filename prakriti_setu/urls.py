from django.urls import path
from . import views

urlpatterns = [
    path('api/register/', views.register_user, name='register'),
    path('api/login/', views.login_user, name='login'),
    path('api/logout/', views.logout_user, name='logout'),
    path('api/user/', views.get_user, name='get_user'),
    path('api/user/update/', views.update_user, name='update_user'),
]