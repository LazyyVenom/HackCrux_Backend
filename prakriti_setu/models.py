from django.db import models
from django.utils.translation import gettext_lazy as _

class User(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(_('email address'), unique=True)
    password = models.CharField(max_length=128)  # Add this line for password
    name = models.CharField(_('name'), max_length=150, blank=True)
    bio = models.TextField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    is_volunteer = models.BooleanField(default=False)
    is_organization = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        app_label = 'prakriti_setu'

    def __str__(self):
        return self.username


class SosAlert(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('false_alarm', 'False Alarm'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sos_alerts')
    latitude = models.FloatField()
    longitude = models.FloatField()
    location_name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    message = models.TextField(blank=True, null=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'SOS Alert'
        verbose_name_plural = 'SOS Alerts'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"SOS from {self.user.username} at {self.created_at}"
