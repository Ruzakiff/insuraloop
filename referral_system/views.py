from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
import random
import string
from .models import ReferralLink
from django.urls import reverse

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
        return redirect('referral_system:my_referral_links')
    
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
    """Download a QR code for a referral link"""
    link = get_object_or_404(ReferralLink, id=link_id, user=request.user)
    
    # Generate the QR code
    buffer = link.generate_qr_code(request)
    
    # Create response
    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response['Content-Disposition'] = f'attachment; filename="qrcode-{link.code}.png"'
    
    return response

@login_required
def view_qr_code(request, link_id):
    """View a QR code for a referral link with print options"""
    link = get_object_or_404(ReferralLink, id=link_id, user=request.user)
    return render(request, 'referral_system/qr_code.html', {'link': link})
