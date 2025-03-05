from django.db import models
from django.conf import settings
from referral_system.models import ReferralLink

class Lead(models.Model):
    """Information about a potential customer (lead)"""
    # Basic information
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    
    # Insurance details
    INSURANCE_TYPE_CHOICES = [
        ('auto', 'Auto Insurance'),
        ('home', 'Home Insurance'),
        ('life', 'Life Insurance'),
        ('health', 'Health Insurance'),
        ('business', 'Business Insurance'),
        ('other', 'Other'),
    ]
    insurance_type = models.CharField(max_length=20, choices=INSURANCE_TYPE_CHOICES)
    notes = models.TextField(blank=True, null=True)
    
    # Referral tracking
    referral_link = models.ForeignKey(ReferralLink, on_delete=models.SET_NULL, null=True, related_name='leads')
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='leads')
    
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
