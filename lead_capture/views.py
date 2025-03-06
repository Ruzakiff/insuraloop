from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from referral_system.models import ReferralLink
from .forms import LeadCaptureForm
from .models import Lead
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
import json

@require_http_methods(["GET", "POST"])
def lead_capture(request, code):
    """Capture leads from referral links"""
    # Get the referral link or 404
    link = get_object_or_404(ReferralLink, code=code, is_active=True)
    
    # For GET requests, increment the click counter
    if request.method == 'GET':
        link.increment_clicks()
    
    if request.method == 'POST':
        # Create the lead from form data
        lead = Lead(
            referral_link=link,
            agent=link.user,  # Assign the agent who created the link
            
            # Basic information
            name=request.POST.get('name', ''),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            insurance_type=request.POST.get('insurance_type', ''),
            
            # Additional information based on insurance type
            zip_code=request.POST.get('zip_code', ''),
            address=request.POST.get('address', ''),
            notes=request.POST.get('notes', ''),
            
            # Contact preferences
            preferred_contact_method=request.POST.get('preferred_contact_method', 'phone'),
            preferred_time=request.POST.get('preferred_time', ''),
            
            # Tracking information
            ip_address=request.META.get('REMOTE_ADDR', None),
            user_agent=request.META.get('HTTP_USER_AGENT', None),
        )
        
        # Add insurance type specific fields
        if request.POST.get('insurance_type') == 'auto':
            lead.vehicle_vin = request.POST.get('vehicle_vin', '')
            lead.vehicle_year = request.POST.get('vehicle_year', None)
            lead.vehicle_make = request.POST.get('vehicle_make', '')
            lead.vehicle_model = request.POST.get('vehicle_model', '')
            lead.date_of_birth = request.POST.get('date_of_birth', None)
            lead.current_insurer = request.POST.get('current_insurer', '')
            lead.vehicle_usage = request.POST.get('vehicle_usage', '')
            lead.annual_mileage = request.POST.get('annual_mileage', None)
            
        elif request.POST.get('insurance_type') == 'home':
            lead.property_type = request.POST.get('property_type', '')
            lead.ownership_status = request.POST.get('ownership_status', '')
            lead.year_built = request.POST.get('year_built', None)
            lead.square_footage = request.POST.get('square_footage', None)
            lead.current_insurer = request.POST.get('current_insurer', '')
            lead.num_bedrooms = request.POST.get('num_bedrooms', None)
            lead.num_bathrooms = request.POST.get('num_bathrooms', None)
            
        elif request.POST.get('insurance_type') == 'business':
            lead.business_name = request.POST.get('business_name', '')
            lead.business_address = request.POST.get('business_address', '')
            lead.industry = request.POST.get('industry', '')
            lead.num_employees = request.POST.get('num_employees', None)
            lead.annual_revenue = request.POST.get('annual_revenue', '')
            lead.current_insurer = request.POST.get('current_insurer', '')
        
        # Save the lead
        lead.save()
        
        # Increment conversions
        link.increment_conversions()
        
        # Redirect to thank you page
        return redirect('lead_capture:thank_you', lead_id=lead.id)
    
    # GET request - display the form
    return render(request, 'lead_capture/lead_form.html', {'code': code})

@require_http_methods(["GET", "POST"])
def step2_basic_info(request, code):
    """Second step - basic information based on insurance type"""
    # Get the referral link or 404
    link = get_object_or_404(ReferralLink, code=code, is_active=True)
    
    # Get insurance type from session
    insurance_type = request.session.get('insurance_type')
    if not insurance_type:
        return redirect('lead_capture:lead_form', code=code)
        
    if request.method == 'POST':
        # Store data in session
        for key, value in request.POST.items():
            request.session[key] = value
            
        # Redirect to next step
        return redirect('lead_capture:step3', code=code)
        
    # Render the appropriate template based on insurance type
    template = f'lead_capture/step2_{insurance_type}.html'
    return render(request, template, {'code': code, 'insurance_type': insurance_type})

@require_http_methods(["GET", "POST"])
def step3_contact_info(request, code):
    """Third step - contact information"""
    # Get the referral link or 404
    link = get_object_or_404(ReferralLink, code=code, is_active=True)
    
    # Get insurance type from session
    insurance_type = request.session.get('insurance_type')
    if not insurance_type:
        return redirect('lead_capture:lead_form', code=code)
        
    if request.method == 'POST':
        # Store data in session
        for key, value in request.POST.items():
            request.session[key] = value
            
        # Redirect to final step
        return redirect('lead_capture:step4', code=code)
        
    return render(request, 'lead_capture/step3_contact.html', {
        'code': code, 
        'insurance_type': insurance_type
    })

@require_http_methods(["GET", "POST"])
def step4_confirmation(request, code):
    """Final step - review and confirm submission"""
    # Get the referral link or 404
    link = get_object_or_404(ReferralLink, code=code, is_active=True)
    
    # Get insurance type from session
    insurance_type = request.session.get('insurance_type')
    if not insurance_type:
        return redirect('lead_capture:lead_form', code=code)
        
    if request.method == 'POST':
        # Create the lead from session data
        lead = Lead(
            referral_link=link,
            agent=link.user,
            insurance_type=insurance_type,
            
            # Basic info
            name=request.session.get('name', ''),
            email=request.session.get('email', ''),
            phone=request.session.get('phone', ''),
            
            # Common fields
            zip_code=request.session.get('zip_code', ''),
            notes=request.session.get('notes', ''),
            
            # Contact preferences
            preferred_contact_method=request.session.get('preferred_contact_method', 'phone'),
            preferred_time=request.session.get('preferred_time', ''),
            
            # Tracking information
            ip_address=request.META.get('REMOTE_ADDR', None),
            user_agent=request.META.get('HTTP_USER_AGENT', None),
        )
        
        # Add type-specific fields
        if insurance_type == 'auto':
            lead.vehicle_vin = request.session.get('vehicle_vin', '')
            lead.vehicle_year = request.session.get('vehicle_year', None) 
            lead.vehicle_make = request.session.get('vehicle_make', '')
            lead.vehicle_model = request.session.get('vehicle_model', '')
            lead.date_of_birth = request.session.get('date_of_birth', None)
            lead.current_insurer = request.session.get('current_insurer', '')
            
        elif insurance_type == 'home':
            lead.address = request.session.get('address', '')
            lead.property_type = request.session.get('property_type', '')
            lead.ownership_status = request.session.get('ownership_status', '')
            lead.year_built = request.session.get('year_built', None)
            lead.square_footage = request.session.get('square_footage', None)
            
        elif insurance_type == 'business':
            lead.business_name = request.session.get('business_name', '')
            lead.industry = request.session.get('industry', '')
            lead.num_employees = request.session.get('num_employees', None)
            lead.annual_revenue = request.session.get('annual_revenue', '')
            
        # Save the lead
        lead.save()
        
        # Record the conversion for the referral link
        link.increment_conversions()
        
        # Clear the session data
        for key in list(request.session.keys()):
            if not key.startswith('_'):  # Don't remove Django's session keys
                del request.session[key]
        
        # Redirect to thank you page
        return redirect('lead_capture:thank_you', lead_id=lead.id)
        
    # Gather all session data for the summary
    form_data = {k: v for k, v in request.session.items() if not k.startswith('_')}
    
    return render(request, 'lead_capture/step4_confirmation.html', {
        'code': code,
        'insurance_type': insurance_type,
        'form_data': form_data
    })

def thank_you(request, lead_id):
    """Thank you page after lead submission"""
    # Get the lead
    lead = get_object_or_404(Lead, id=lead_id)
    
    # Render the thank you page
    return render(request, 'lead_capture/thank_you.html', {
        'lead': lead,
        'agent': lead.agent,
    })

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
