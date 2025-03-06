from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
import random
import string
from .models import ReferralLink
from lead_capture.models import Lead
from django.urls import reverse
import qrcode
import io
import base64

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
def my_referral_links(request):
    """Display all referral links for the current user"""
    links = ReferralLink.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'referral_system/my_links.html', {'links': links})

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

def my_links(request):
    """View all referral links for the logged-in user"""
    links = ReferralLink.objects.filter(user=request.user).order_by('-created_at')
    
    # Calculate totals
    total_clicks = sum(link.clicks for link in links)
    total_conversions = sum(link.conversions for link in links)
    
    # Calculate conversion rate
    conversion_rate = 0
    if total_clicks > 0:
        conversion_rate = (total_conversions / total_clicks) * 100
    
    # Calculate conversion rate for each link
    for link in links:
        if link.clicks > 0:
            link.conversion_rate = (link.conversions / link.clicks) * 100
        else:
            link.conversion_rate = 0
    
    # Add totals to links
    links.total_clicks = total_clicks
    links.total_conversions = total_conversions
    links.conversion_rate = conversion_rate
    
    return render(request, 'referral_system/my_links.html', {'links': links})

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
