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
    
    def __str__(self):
        return f"Referral link for {self.user.username} ({self.code})"
    
    def get_absolute_url(self):
        return reverse('referral_system:referral_landing', kwargs={'code': self.code})
    
    def generate_full_url(self, request=None):
        if request:
            return request.build_absolute_uri(self.get_absolute_url())
        return f"{settings.SITE_URL}{self.get_absolute_url()}"
