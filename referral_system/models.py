import uuid
from django.db import models
from django.conf import settings
from django.urls import reverse
from decimal import Decimal
import qrcode
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys

# Create your models here.

class ReferralLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referral_links')
    code = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    clicks = models.IntegerField(default=0)
    visits = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    
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
    
    # Add a referral type field
    REFERRAL_TYPE_CHOICES = [
        ('business', 'Business Partner'),
        ('customer', 'Existing Customer'),
        ('agent', 'Direct from Agent'),
    ]
    referral_type = models.CharField(
        max_length=20, 
        choices=REFERRAL_TYPE_CHOICES,
        default='agent',
        help_text="Who is sharing this referral link"
    )
    
    # If it's a customer referral, we can store customer info
    customer_name = models.CharField(max_length=100, blank=True, null=True, 
                                     help_text="Name of existing customer making the referral")
    customer_email = models.EmailField(blank=True, null=True,
                                      help_text="Email of existing customer making the referral")
    
    def __str__(self):
        return f"Referral link for {self.user.username} ({self.code})"
    
    def get_absolute_url(self):
        return reverse('referral_system:referral_landing', kwargs={'code': self.code})
    
    def generate_full_url(self, request=None):
        if request:
            return request.build_absolute_uri(self.get_absolute_url())
        return f"{settings.SITE_URL}{self.get_absolute_url()}"

    def get_reward_amount(self):
        """Calculate reward amount based on referral type"""
        if self.referral_type == 'business':
            return Decimal('50.00')  # Higher reward for business partners
        elif self.referral_type == 'customer':
            return Decimal('25.00')  # Smaller reward for customers
        else:
            return Decimal('0.00')   # No reward for direct agent referrals

    def generate_qr_code(self, request=None):
        """Generate a QR code for this referral link"""
        # Get the full URL for the referral link
        url = self.generate_full_url(request)
        
        # Create QR code instance
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Add data
        qr.add_data(url)
        qr.make(fit=True)
        
        # Create an image from the QR Code instance
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Create a BytesIO buffer to hold the image
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)  # Go to the start of the buffer
        
        return buffer

    def increment_conversions(self):
        """Increment the conversion count for this referral link"""
        self.conversions += 1
        self.save(update_fields=['conversions'])
        return self.conversions
