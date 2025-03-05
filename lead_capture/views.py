from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from referral_system.models import ReferralLink
from .forms import LeadCaptureForm
from .models import Lead
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

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

@login_required
def test_email(request, lead_id):
    """Test view to manually trigger email for a lead"""
    # Get the lead or return 404
    lead = get_object_or_404(Lead, id=lead_id)
    
    # Check if the lead has an agent
    if not lead.agent:
        # Assign the current user as the agent if none is assigned
        lead.agent = request.user
        lead.save()
        message = "Note: This lead didn't have an agent assigned, so you were assigned as the agent."
    else:
        message = ""
    
    # Check if the agent has an email
    if not lead.agent.email:
        return HttpResponse(f"Error: The assigned agent ({lead.agent.username}) doesn't have an email address. "
                            f"Please add an email address to the agent's profile.")
    
    # Import and call the signal function directly
    from .signals import notify_agent_of_new_lead
    notify_agent_of_new_lead(sender=Lead, instance=lead, created=True)
    
    return HttpResponse(f"{message} Test email sent to {lead.agent.email} for lead: {lead.name}!")
