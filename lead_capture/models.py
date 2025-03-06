from django.db import models
from django.conf import settings
from referral_system.models import ReferralLink
from django.contrib.auth.models import User

class Lead(models.Model):
    """Information about a potential customer (lead)"""
    # Basic information
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    
    # Insurance details
    INSURANCE_TYPE_CHOICES = [
        ('auto', 'Auto Insurance'),
        ('home', 'Home Insurance'),
        ('business', 'Business Insurance'),
        ('life', 'Life Insurance'),
        ('health', 'Health Insurance'),
        ('other', 'Other'),
    ]
    insurance_type = models.CharField(max_length=20, choices=INSURANCE_TYPE_CHOICES)
    
    # Extended fields for Auto Insurance
    zip_code = models.CharField(max_length=10, blank=True, null=True)
    vehicle_vin = models.CharField(max_length=17, blank=True, null=True, verbose_name="VIN")
    vehicle_year = models.IntegerField(blank=True, null=True)
    vehicle_make = models.CharField(max_length=50, blank=True, null=True)
    vehicle_model = models.CharField(max_length=50, blank=True, null=True)
    vehicle_usage = models.CharField(max_length=20, blank=True, null=True)
    annual_mileage = models.IntegerField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    current_insurer = models.CharField(max_length=100, blank=True, null=True)
    
    # Extended fields for Home Insurance
    address = models.CharField(max_length=255, blank=True, null=True)
    property_type = models.CharField(max_length=50, blank=True, null=True)
    ownership_status = models.CharField(max_length=20, blank=True, null=True)  # Own or Rent
    year_built = models.IntegerField(blank=True, null=True)
    square_footage = models.IntegerField(blank=True, null=True)
    num_bedrooms = models.IntegerField(blank=True, null=True)
    num_bathrooms = models.IntegerField(blank=True, null=True)
    
    # Extended fields for Business Insurance
    business_name = models.CharField(max_length=255, blank=True, null=True)
    business_address = models.CharField(max_length=255, blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    num_employees = models.IntegerField(blank=True, null=True)
    annual_revenue = models.CharField(max_length=50, blank=True, null=True)
    
    # Common fields
    notes = models.TextField(blank=True, null=True)
    preferred_contact_method = models.CharField(
        max_length=20, 
        choices=[('email', 'Email'), ('phone', 'Phone'), ('text', 'Text Message')],
        default='phone'
    )
    preferred_time = models.CharField(
        max_length=20, 
        choices=[('morning', 'Morning'), ('afternoon', 'Afternoon'), ('evening', 'Evening')],
        blank=True, 
        null=True
    )
    
    # Tracking fields
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    is_duplicate = models.BooleanField(default=False)
    
    # Status tracking
    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('quoted', 'Quote Completed'),
        ('converted', 'Policy Purchased'),
        ('closed', 'Closed (No Sale)'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Reward tracking
    reward_sent = models.BooleanField(default=False)
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Referral tracking
    referral_link = models.ForeignKey(ReferralLink, on_delete=models.SET_NULL, null=True, related_name='leads')
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='leads')
    
    def __str__(self):
        return f"{self.name} - {self.get_insurance_type_display()} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        # If this is a new lead, set the agent from the referral link
        if not self.pk and self.referral_link and not self.agent:
            self.agent = self.referral_link.user
            
        # If this is a new lead, set the reward amount
        if not self.pk and self.referral_link and not self.reward_amount:
            self.reward_amount = self.referral_link.get_reward_amount()
            
        super().save(*args, **kwargs)
