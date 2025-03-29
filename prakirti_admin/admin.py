from django.contrib import admin
from .models import Admin

# Register the Admin model with the Django admin site
@admin.register(Admin)
class AdminModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'created_at')
    search_fields = ('name', 'email')
    list_filter = ('created_at',)
