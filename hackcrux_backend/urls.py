from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", include('prakriti_setu.urls')),
    path("api/admin/", include('prakirti_admin.urls')),
]
