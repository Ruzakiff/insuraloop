from django.db import models

class ValidationSetting(models.Model):
    """Configuration settings for lead validation"""
    # Thresholds
    high_quality_threshold = models.IntegerField(default=80, help_text="Minimum score for high quality leads")
    medium_quality_threshold = models.IntegerField(default=50, help_text="Minimum score for medium quality leads")
    
    # Weight of different validation components
    email_weight = models.IntegerField(default=40, help_text="Maximum points for email validation")
    phone_weight = models.IntegerField(default=30, help_text="Maximum points for phone validation")
    location_weight = models.IntegerField(default=15, help_text="Maximum points for location validation")
    name_weight = models.IntegerField(default=15, help_text="Maximum points for name validation")
    
    # Disposable email domain list
    disposable_domains = models.TextField(
        blank=True,
        help_text="Comma-separated list of disposable email domains to block"
    )
    
    # Auto-rejection settings
    reject_disposable_emails = models.BooleanField(default=True)
    reject_invalid_phones = models.BooleanField(default=True)
    
    # Only have one active configuration
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Ensure only one active configuration
        if self.is_active:
            # Set all other configurations to inactive
            ValidationSetting.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active(cls):
        """Get the active configuration or create default if none exists"""
        active = cls.objects.filter(is_active=True).first()
        if not active:
            active = cls.objects.create(
                is_active=True,
                disposable_domains="mailinator.com,tempmail.com,fakeinbox.com,yopmail.com,guerrillamail.com"
            )
        return active
    
    def __str__(self):
        return f"Validation Settings (Updated: {self.updated_at.strftime('%Y-%m-%d')})"


class ValidationLog(models.Model):
    """Log of all validation requests and results"""
    lead_id = models.IntegerField(blank=True, null=True, help_text="ID of the lead if created")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    
    # Validation results
    score = models.IntegerField(default=0)
    validated_at = models.DateTimeField(auto_now_add=True)
    results = models.JSONField(blank=True, null=True, help_text="Full validation results")
    
    # Why was lead rejected or flagged?
    rejection_reason = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return f"Validation #{self.id} - Score: {self.score} - {self.validated_at.strftime('%Y-%m-%d %H:%M')}" 