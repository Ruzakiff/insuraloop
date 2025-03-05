import uuid
from django.db import models
from django.conf import settings
from django.urls import reverse

# Create your models here.

class ReferralLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referral_links')
    code = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    clicks = models.IntegerField(default=0)
    
    # New fields with defaults
    name = models.CharField(max_length=100, help_text="Name this link for your reference", default="My Referral Link")
    partner_name = models.CharField(max_length=100, blank=True, null=True, help_text="Business partner using this link")
    insurance_type = models.CharField(max_length=50, choices=[
        ('auto', 'Auto Insurance'),
        ('home', 'Home Insurance'),
        ('life', 'Life Insurance'),
        ('health', 'Health Insurance'),
        ('business', 'Business Insurance'),
        ('other', 'Other')
    ], default='auto')
    source = models.CharField(max_length=50, choices=[
        ('website', 'Your Website'),
        ('email', 'Email Campaign'),
        ('social', 'Social Media'),
        ('partner', 'Business Partner'),
        ('print', 'Print Materials'),
        ('other', 'Other')
    ], default='website')
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Referral link for {self.user.username} ({self.code})"
    
    def get_absolute_url(self):
        return reverse('referral_system:referral_landing', kwargs={'code': self.code})
    
    def generate_full_url(self, request=None):
        if request:
            return request.build_absolute_uri(self.get_absolute_url())
        return f"{settings.SITE_URL}{self.get_absolute_url()}"
