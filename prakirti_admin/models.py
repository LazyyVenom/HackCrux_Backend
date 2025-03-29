from django.db import models

class Admin(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class VolunteeringEvent(models.Model):
    CATEGORY_CHOICES = [
        ('planting', 'Tree Planting'),
        ('cleanup', 'Cleanup'),
        ('gardening', 'Gardening'),
        ('education', 'Education'),
        ('disaster', 'Disaster Management'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateField()
    time = models.CharField(max_length=50)
    location = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='planting')
    spots_total = models.PositiveIntegerField(default=20)
    organizer = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
    @property
    def spots_filled(self):
        return self.registrations.filter(status='confirmed').count()
    
    @property
    def spots_remaining(self):
        return self.spots_total - self.spots_filled

class EventRegistration(models.Model):
    STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('waitlisted', 'Waitlisted'),
        ('cancelled', 'Cancelled'),
    ]
    
    event = models.ForeignKey(VolunteeringEvent, on_delete=models.CASCADE, related_name='registrations')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    registration_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed')
    
    def __str__(self):
        return f"{self.name} - {self.event.title}"

class DonationField(models.Model):
    """Represents different areas/fields where users can donate"""
    title = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="Icon name for frontend display")
    color = models.CharField(max_length=20, help_text="Color code for frontend styling", default="indigo")
    target_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
    @property
    def raised_amount(self):
        """Calculate total amount raised for this field"""
        return self.donations.filter(status='completed').aggregate(
            total=models.Sum('amount')
        )['total'] or 0
    
    @property
    def progress_percentage(self):
        """Calculate percentage of target reached"""
        if self.target_amount == 0:
            return 0
        return min(100, int((self.raised_amount / self.target_amount) * 100))

class Donation(models.Model):
    """Tracks individual donations made by users"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    donation_field = models.ForeignKey(DonationField, on_delete=models.CASCADE, related_name='donations')
    user = models.ForeignKey('prakriti_setu.User', on_delete=models.SET_NULL, null=True, blank=True)
    donor_name = models.CharField(max_length=100, blank=True)
    donor_email = models.EmailField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    qr_code_id = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_anonymous = models.BooleanField(default=False)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        if self.is_anonymous:
            return f"Anonymous - {self.donation_field.title} - {self.amount}"
        return f"{self.donor_name or 'Unknown'} - {self.donation_field.title} - {self.amount}"


class ResourceCapacity(models.Model):
    """Tracks the capacity of resources available for events"""
    resource_type = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    total_capacity = models.PositiveIntegerField()
    available_capacity = models.PositiveIntegerField()
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.resource_type} - {self.location}"