from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from referral_system.models import ReferralLink
from .forms import LeadCaptureForm
from .models import Lead

def lead_capture(request, code):
    """Display and process the lead capture form"""
    # Get the referral link that was used
    link = get_object_or_404(ReferralLink, code=code, is_active=True)
    
    # Increment the click counter
    link.clicks += 1
    link.save()
    
    if request.method == 'POST':
        form = LeadCaptureForm(request.POST)
        if form.is_valid():
            # Create the lead but don't save to DB yet
            lead = form.save(commit=False)
            
            # Add referral information
            lead.referral_link = link
            lead.agent = link.user
            
            # Save to database
            lead.save()
            
            # Show success message
            messages.success(request, "Thank you! An insurance agent will contact you soon.")
            
            # Redirect to thank you page
            return redirect(reverse('lead_capture:thank_you', kwargs={'lead_id': lead.id}))
    else:
        # Display blank form for GET request
        form = LeadCaptureForm()
    
    # Determine who made the referral for the template
    context = {
        'form': form,
        'link': link,
    }
    
    return render(request, 'lead_capture/lead_form.html', context)

def thank_you(request, lead_id):
    """Thank you page after lead submission"""
    lead = get_object_or_404(Lead, id=lead_id)
    
    return render(request, 'lead_capture/thank_you.html', {'lead': lead})
