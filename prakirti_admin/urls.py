from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('login/', views.admin_login, name='admin_login'),
    path('register/', views.admin_register, name='admin_register'),
    path('logout/', views.admin_logout, name='admin_logout'),
]