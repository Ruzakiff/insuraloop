import uuid
from django.db import models
from django.conf import settings
from django.urls import reverse
from decimal import Decimal
import qrcode
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
from django.contrib.auth.models import User

# Create your models here.

class ReferralLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referral_links')
    code = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    clicks = models.PositiveIntegerField(default=0)
    visits = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    paid_conversions = models.PositiveIntegerField(default=0)
    
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
    
    # State targeting for payment rates
    STATE_CHOICES = [
        ('', 'Nationwide (Default Rate)'),
        ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'), ('AR', 'Arkansas'),
        ('CA', 'California'), ('CO', 'Colorado'), ('CT', 'Connecticut'), ('DE', 'Delaware'),
        ('FL', 'Florida'), ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'),
        ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'), ('KS', 'Kansas'),
        ('KY', 'Kentucky'), ('LA', 'Louisiana'), ('ME', 'Maine'), ('MD', 'Maryland'),
        ('MA', 'Massachusetts'), ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'),
        ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'), ('NV', 'Nevada'),
        ('NH', 'New Hampshire'), ('NJ', 'New Jersey'), ('NM', 'New Mexico'), ('NY', 'New York'),
        ('NC', 'North Carolina'), ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'),
        ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'), ('SC', 'South Carolina'),
        ('SD', 'South Dakota'), ('TN', 'Tennessee'), ('TX', 'Texas'), ('UT', 'Utah'),
        ('VT', 'Vermont'), ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'),
        ('WI', 'Wisconsin'), ('WY', 'Wyoming'), ('DC', 'District of Columbia'),
    ]
    target_state = models.CharField(max_length=2, choices=STATE_CHOICES, blank=True, null=True)
    
    # For tracking payments
    earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
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

    def increment_clicks(self):
        """Increment the click count for this referral link"""
        self.clicks += 1
        self.save(update_fields=['clicks'])
        return self.clicks

    def increment_conversions(self):
        """Increment the conversion count for this referral link"""
        self.conversions += 1
        self.save(update_fields=['conversions'])
        return self.conversions

    @property
    def conversion_rate(self):
        """Calculate the conversion rate for this link"""
        if self.clicks == 0:
            return 0
        return (self.conversions / self.clicks) * 100

class PaymentRate(models.Model):
    """Stores payment rates for different states and insurance types"""
    STATE_CHOICES = ReferralLink.STATE_CHOICES
    
    state = models.CharField(max_length=2, choices=STATE_CHOICES, blank=True, default='')
    
    INSURANCE_TYPE_CHOICES = [
        ('auto', 'Auto Insurance'),
        ('home', 'Home Insurance'),
        ('business', 'Business Insurance'),
        ('life', 'Life Insurance'),
        ('health', 'Health Insurance'),
        ('other', 'Other'),
    ]
    insurance_type = models.CharField(max_length=20, choices=INSURANCE_TYPE_CHOICES, default='auto')
    
    # Base rates
    rate_amount = models.DecimalField(max_digits=6, decimal_places=2)
    
    # Effective dates
    effective_from = models.DateField(auto_now_add=True)
    effective_to = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('state', 'insurance_type')
        
    def __str__(self):
        state_name = dict(self.STATE_CHOICES).get(self.state, 'Nationwide')
        insurance_name = dict(self.INSURANCE_TYPE_CHOICES).get(self.insurance_type, 'Other')
        return f"{state_name} - {insurance_name}: ${self.rate_amount}"

class AgentPaymentPreference(models.Model):
    """Stores agent preferences for referral payments"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='payment_preferences')
    
    # Global preferences
    default_rate = models.DecimalField(max_digits=10, decimal_places=2, default=25.00,
                                    help_text="Default payment rate when no specific rate applies")
    
    # Payment method preferences
    PAYMENT_METHOD_CHOICES = [
        ('direct_deposit', 'Direct Deposit'),
        ('paypal', 'PayPal'),
        ('check', 'Check'),
        ('venmo', 'Venmo'),
        ('zelle', 'Zelle'),
    ]
    preferred_payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='direct_deposit')
    
    # Payment account info (encrypted in production)
    payment_email = models.EmailField(blank=True, null=True, 
                                help_text="Email address for PayPal, Venmo, etc.")
    account_number = models.CharField(max_length=255, blank=True, null=True,
                                help_text="Account number for direct deposit")
    routing_number = models.CharField(max_length=255, blank=True, null=True,
                                help_text="Routing number for direct deposit")
    
    # Payment schedule preference
    PAYMENT_SCHEDULE_CHOICES = [
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
    ]
    payment_schedule = models.CharField(max_length=10, choices=PAYMENT_SCHEDULE_CHOICES, default='monthly')
    
    # Threshold for payment
    payment_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=50.00,
                                        help_text="Minimum amount before payment is issued")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Payment Preferences for {self.user.username}"

class AgentRateOverride(models.Model):
    """Allows agents to specify custom rates for specific states or insurance types"""
    preference = models.ForeignKey(AgentPaymentPreference, on_delete=models.CASCADE, related_name='rate_overrides')
    
    # What is this override for?
    STATE_CHOICES = ReferralLink.STATE_CHOICES
    state = models.CharField(max_length=2, choices=STATE_CHOICES, blank=True, null=True,
                            help_text="State this rate applies to (leave blank for all states)")
    
    INSURANCE_TYPE_CHOICES = [
        ('', 'All Insurance Types'),
        ('auto', 'Auto Insurance'),
        ('home', 'Home Insurance'),
        ('business', 'Business Insurance'),
        ('life', 'Life Insurance'),
        ('health', 'Health Insurance'),
        ('other', 'Other'),
    ]
    insurance_type = models.CharField(max_length=20, choices=INSURANCE_TYPE_CHOICES, blank=True, default='',
                                    help_text="Insurance type this rate applies to (leave blank for all types)")
    
    # The custom rate
    rate = models.DecimalField(max_digits=10, decimal_places=2,
                            help_text="Custom rate for this specific combination")
    
    # Is this override active?
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('preference', 'state', 'insurance_type')
    
    def __str__(self):
        state_name = dict(self.STATE_CHOICES).get(self.state, 'All States') if self.state else 'All States'
        insurance_name = dict(self.INSURANCE_TYPE_CHOICES).get(self.insurance_type, 'All Types') if self.insurance_type else 'All Types'
        return f"{state_name} - {insurance_name}: ${self.rate}"
