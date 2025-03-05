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
    link = get_object_or_404(ReferralLink, code=code, is_active=True)
    link.clicks += 1
    link.save()
    
    # Store referral info in session for attribution
    request.session['referral_code'] = code
    request.session['referrer_id'] = str(link.user.id)
    
    # For now, just show a placeholder page
    return render(request, 'referral_system/lead_capture_placeholder.html', {'link': link})

@login_required
def generate_referral_link(request):
    """Generate a new referral link for the current user"""
    if request.method == 'POST':
        code = generate_unique_code()
        link = ReferralLink.objects.create(
            user=request.user,
            code=code
        )
        
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
