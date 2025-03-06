from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
import random
import string
from .models import ReferralLink, AgentPaymentPreference, AgentRateOverride
from lead_capture.models import Lead
from django.urls import reverse
import qrcode
import io
import base64
from django.contrib import messages

# Create your views here.

def generate_unique_code(length=8):
    """Generate a random alphanumeric code of specified length"""
    chars = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choice(chars) for _ in range(length))
        if not ReferralLink.objects.filter(code=code).exists():
            return code

def referral_landing(request, code):
    """Landing page for referral links - now redirects to lead capture form"""
    # Get the referral link
    link = get_object_or_404(ReferralLink, code=code, is_active=True)
    
    # Store referral info in session for attribution
    request.session['referral_code'] = code
    request.session['referrer_id'] = str(link.user.id)
    
    # Redirect to the lead capture form in the new app
    return redirect('lead_capture:lead_form', code=code)

@login_required
def generate_referral_link(request):
    """Generate a new referral link for the current user"""
    if request.method == 'POST':
        code = generate_unique_code()
        
        # Extract form data
        name = request.POST.get('name', 'My Referral Link')
        referral_type = request.POST.get('referral_type', 'agent')
        insurance_type = request.POST.get('insurance_type', 'auto')
        source = request.POST.get('source', 'website')
        notes = request.POST.get('notes', None)
        
        # Get type-specific data
        partner_name = None
        customer_name = None
        customer_email = None
        
        if referral_type == 'business':
            partner_name = request.POST.get('partner_name')
        elif referral_type == 'customer':
            customer_name = request.POST.get('customer_name')
            customer_email = request.POST.get('customer_email')
        
        # Create the link
        link = ReferralLink.objects.create(
            user=request.user,
            code=code,
            name=name,
            referral_type=referral_type,
            partner_name=partner_name,
            customer_name=customer_name,
            customer_email=customer_email,
            insurance_type=insurance_type,
            source=source,
            notes=notes
        )
        
        # Debug output
        print(f"Created link: {link.id} - Type: {link.referral_type}, Partner: {link.partner_name}, Customer: {link.customer_name}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'code': code,
                'full_url': link.generate_full_url(request),
                'qr_url': reverse('referral_system:view_qr_code', kwargs={'link_id': link.id})
            })
        return redirect('referral_system:my_links')
    
    return render(request, 'referral_system/generate_link.html')

@login_required
def my_links(request):
    """View all referral links for the logged-in user"""
    links = ReferralLink.objects.filter(user=request.user).order_by('-created_at')
    
    # Calculate totals
    total_clicks = sum(link.clicks for link in links)
    total_conversions = sum(link.conversions for link in links)
    total_earnings = sum(link.earnings for link in links)
    
    # Calculate conversion rate
    conversion_rate = 0
    if total_clicks > 0:
        conversion_rate = (total_conversions / total_clicks) * 100
    
    # Add totals to links
    links.total_clicks = total_clicks
    links.total_conversions = total_conversions
    links.conversion_rate = conversion_rate
    links.total_earnings = total_earnings
    
    return render(request, 'referral_system/my_links.html', {'links': links})

# Add an alias for backward compatibility
my_referral_links = my_links  # This ensures old references to my_referral_links still work

def disclaimer(request):
    """Display the legal disclaimer page"""
    return render(request, 'referral_system/disclaimer.html')

@login_required
def download_qr_code(request, link_id):
    """Download QR code for a specific referral link"""
    link = get_object_or_404(ReferralLink, id=link_id, user=request.user)
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(link.generate_full_url(request))
    qr.make(fit=True)
    
    # Create QR code image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to BytesIO
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    # Create response
    response = HttpResponse(buffer, content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="qr_code_{link.code}.png"'
    
    return response

@login_required
def view_qr_code(request, link_id):
    """View QR code for a specific referral link"""
    link = get_object_or_404(ReferralLink, id=link_id, user=request.user)
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(link.generate_full_url(request))
    qr.make(fit=True)
    
    # Create QR code image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to BytesIO and encode as base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    qr_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return render(request, 'referral_system/qr_code.html', {
        'link': link,
        'qr_image': qr_image
    })

def view_leads(request, link_id):
    """View leads for a specific referral link"""
    link = get_object_or_404(ReferralLink, id=link_id, user=request.user)
    leads = Lead.objects.filter(referral_link=link).order_by('-created_at')
    
    return render(request, 'referral_system/view_leads.html', {'link': link, 'leads': leads})

def view_lead_details(request, lead_id):
    """View detailed information for a specific lead"""
    # Make sure the lead belongs to the current user
    lead = get_object_or_404(Lead, id=lead_id, referral_link__user=request.user)
    
    return render(request, 'referral_system/lead_details.html', {'lead': lead})

@login_required
def payment_preferences(request):
    """View and update payment preferences"""
    # Get or create the user's payment preferences
    preferences, created = AgentPaymentPreference.objects.get_or_create(user=request.user)
    
    # Get all active rate overrides
    overrides = AgentRateOverride.objects.filter(preference=preferences, is_active=True)
    
    # Group overrides by type for easier display
    state_overrides = {}
    insurance_overrides = {}
    specific_overrides = {}
    
    for override in overrides:
        if override.state and not override.insurance_type:
            # State-specific override for all insurance types
            state_overrides[override.state] = override
        elif override.insurance_type and not override.state:
            # Insurance-specific override for all states
            insurance_overrides[override.insurance_type] = override
        elif override.state and override.insurance_type:
            # Specific state+insurance combination
            key = f"{override.state}_{override.insurance_type}"
            specific_overrides[key] = override
    
    if request.method == 'POST':
        if 'save_preferences' in request.POST:
            # Update general preferences
            preferences.default_rate = request.POST.get('default_rate', 25.00)
            preferences.preferred_payment_method = request.POST.get('payment_method', 'direct_deposit')
            preferences.payment_email = request.POST.get('payment_email', '')
            preferences.account_number = request.POST.get('account_number', '')
            preferences.routing_number = request.POST.get('routing_number', '')
            preferences.payment_schedule = request.POST.get('payment_schedule', 'monthly')
            preferences.payment_threshold = request.POST.get('payment_threshold', 50.00)
            preferences.save()
            
            messages.success(request, "Payment preferences updated successfully!")
            
        elif 'add_override' in request.POST:
            # Add a new rate override
            state = request.POST.get('override_state', '')
            insurance_type = request.POST.get('override_insurance_type', '')
            rate = request.POST.get('override_rate', 0)
            
            # Validate inputs
            if not rate or float(rate) <= 0:
                messages.error(request, "Please enter a valid rate amount.")
            else:
                # Check if an override already exists
                try:
                    override = AgentRateOverride.objects.get(
                        preference=preferences,
                        state=state if state else None,
                        insurance_type=insurance_type if insurance_type else ''
                    )
                    # Update existing override
                    override.rate = rate
                    override.is_active = True
                    override.save()
                    messages.success(request, "Rate override updated successfully!")
                except AgentRateOverride.DoesNotExist:
                    # Create new override
                    AgentRateOverride.objects.create(
                        preference=preferences,
                        state=state if state else None,
                        insurance_type=insurance_type if insurance_type else '',
                        rate=rate
                    )
                    messages.success(request, "Rate override added successfully!")
                
                return redirect('referral_system:payment_preferences')
                
        elif 'delete_override' in request.POST:
            override_id = request.POST.get('override_id')
            if override_id:
                try:
                    override = AgentRateOverride.objects.get(id=override_id, preference=preferences)
                    override.delete()
                    messages.success(request, "Rate override deleted successfully!")
                except AgentRateOverride.DoesNotExist:
                    messages.error(request, "Rate override not found.")
                
                return redirect('referral_system:payment_preferences')
                
        elif 'bulk_state_update' in request.POST:
            # Update rates for multiple states at once
            states = request.POST.getlist('bulk_states')
            insurance_type = request.POST.get('bulk_insurance_type', '')
            rate = request.POST.get('bulk_rate', 0)
            
            if not states:
                messages.error(request, "Please select at least one state.")
            elif not rate or float(rate) <= 0:
                messages.error(request, "Please enter a valid rate amount.")
            else:
                for state in states:
                    try:
                        override = AgentRateOverride.objects.get(
                            preference=preferences,
                            state=state,
                            insurance_type=insurance_type if insurance_type else ''
                        )
                        # Update existing override
                        override.rate = rate
                        override.is_active = True
                        override.save()
                    except AgentRateOverride.DoesNotExist:
                        # Create new override
                        AgentRateOverride.objects.create(
                            preference=preferences,
                            state=state,
                            insurance_type=insurance_type if insurance_type else '',
                            rate=rate
                        )
                
                messages.success(request, f"Updated rates for {len(states)} states!")
                return redirect('referral_system:payment_preferences')
    
    # Group states by region for easier selection
    regions = {
        'Northeast': ['ME', 'NH', 'VT', 'MA', 'RI', 'CT', 'NY', 'NJ', 'PA'],
        'Midwest': ['OH', 'MI', 'IN', 'IL', 'WI', 'MN', 'IA', 'MO', 'ND', 'SD', 'NE', 'KS'],
        'South': ['DE', 'MD', 'DC', 'VA', 'WV', 'NC', 'SC', 'GA', 'FL', 'KY', 'TN', 'AL', 'MS', 'AR', 'LA', 'OK', 'TX'],
        'West': ['MT', 'ID', 'WY', 'CO', 'NM', 'AZ', 'UT', 'NV', 'WA', 'OR', 'CA', 'AK', 'HI']
    }
    
    return render(request, 'referral_system/payment_preferences.html', {
        'preferences': preferences,
        'state_overrides': state_overrides,
        'insurance_overrides': insurance_overrides,
        'specific_overrides': specific_overrides,
        'regions': regions,
        'states': dict(ReferralLink.STATE_CHOICES),
        'insurance_types': dict(AgentRateOverride.INSURANCE_TYPE_CHOICES),
    })
