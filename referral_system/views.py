from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import random
import string
from .models import ReferralLink

# Create your views here.

def generate_unique_code(length=8):
    """Generate a random alphanumeric code of specified length"""
    chars = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choice(chars) for _ in range(length))
        if not ReferralLink.objects.filter(code=code).exists():
            return code

def referral_landing(request, code):
    """Landing page for referral links"""
    # Explicitly get the link with all fields
    link = get_object_or_404(ReferralLink, code=code, is_active=True)
    link.clicks += 1
    link.save()
    
    # Store referral info in session for attribution
    request.session['referral_code'] = code
    request.session['referrer_id'] = str(link.user.id)
    
    # Add debug information to help troubleshoot
    context = {
        'link': link,
        'debug_partner_name': link.partner_name,  # This will help us see if partner_name exists
    }
    
    # For now, just show a placeholder page
    return render(request, 'referral_system/lead_capture_placeholder.html', context)

@login_required
def generate_referral_link(request):
    """Generate a new referral link for the current user"""
    if request.method == 'POST':
        code = generate_unique_code()
        
        # Extract form data
        name = request.POST.get('name', 'My Referral Link')
        partner_name = request.POST.get('partner_name', None)
        insurance_type = request.POST.get('insurance_type', 'auto')
        source = request.POST.get('source', 'website')
        notes = request.POST.get('notes', None)
        
        # Debug output to console
        print(f"Creating link with: name={name}, partner={partner_name}, type={insurance_type}, source={source}")
        
        # Create the link
        link = ReferralLink.objects.create(
            user=request.user,
            code=code,
            name=name,
            partner_name=partner_name,
            insurance_type=insurance_type,
            source=source,
            notes=notes
        )
        
        # Print the created link details
        print(f"Created link: {link.id} - Partner name: '{link.partner_name}', Source: {link.source}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'code': code,
                'full_url': link.generate_full_url(request)
            })
        return redirect('referral_system:my_referral_links')
    
    return render(request, 'referral_system/generate_link.html')

@login_required
def my_referral_links(request):
    """Display all referral links for the current user"""
    links = ReferralLink.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'referral_system/my_links.html', {'links': links})
