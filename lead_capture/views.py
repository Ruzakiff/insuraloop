from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from referral_system.models import ReferralLink, PaymentRate
from .forms import LeadCaptureForm
from .models import Lead
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
import json
# Import the validation functions
from lead_validation.views import validate_email_address, validate_phone_number, validate_location, validate_name

@require_http_methods(["GET", "POST"])
def lead_capture(request, code):
    """Capture leads from referral links"""
    # Get the referral link or 404
    link = get_object_or_404(ReferralLink, code=code, is_active=True)
    
    # For GET requests, increment the click counter
    if request.method == 'GET':
        link.increment_clicks()
    
    # For POST requests, process the form submission
    if request.method == 'POST':
        # Extract form data
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        
        # Fix: Get the last non-empty ZIP code value
        zip_codes = request.POST.getlist('zip_code')
        zip_code = next((code for code in reversed(zip_codes) if code), '')
        
        print(f"ZIP CODE LIST: {zip_codes}")
        print(f"SELECTED ZIP CODE: '{zip_code}'")
        
        insurance_type = request.POST.get('insurance_type')
        preferred_contact = request.POST.get('preferred_contact', 'phone')
        
        # Debug - print what we're receiving
        print(f"FORM DATA: name={name}, email={email}, phone={phone}")
        print(f"ZIP CODE: '{zip_code}'")  # Print with quotes to see if it's empty or whitespace
        print(f"REQUEST POST DATA: {request.POST}")  # Print all POST data
        
        # Validate required fields
        if not (name and email and phone):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'lead_capture/lead_form.html', {'code': code})
        
        # Create the lead from form data (passing validation)
        lead = Lead(
            referral_link=link,
            agent=link.user,
            name=name,
            email=email,
            phone=phone,
            insurance_type=insurance_type,
            zip_code=zip_code,
            
            # Basic information
            address=request.POST.get('address', ''),
            notes=request.POST.get('notes', ''),
            
            # Contact preferences
            preferred_contact_method=preferred_contact,
            preferred_time=request.POST.get('preferred_time', ''),
            
            # Tracking information
            ip_address=request.META.get('REMOTE_ADDR', None),
            user_agent=request.META.get('HTTP_USER_AGENT', None),
        )
        
        # Debug - print lead object before saving
        print(f"LEAD OBJECT BEFORE SAVE - ZIP CODE: '{lead.zip_code}'")
        
        # Add insurance type specific fields
        if insurance_type == 'auto':
            lead.vehicle_vin = request.POST.get('vehicle_vin', '')
            lead.vehicle_year = request.POST.get('vehicle_year', None)
            lead.vehicle_make = request.POST.get('vehicle_make', '')
            lead.vehicle_model = request.POST.get('vehicle_model', '')
            lead.date_of_birth = request.POST.get('date_of_birth', None)
            lead.current_insurer = request.POST.get('current_insurer', '')
            lead.vehicle_usage = request.POST.get('vehicle_usage', '')
            lead.annual_mileage = request.POST.get('annual_mileage', None)
            
        elif insurance_type == 'home':
            lead.property_type = request.POST.get('property_type', '')
            lead.ownership_status = request.POST.get('ownership_status', '')
            lead.year_built = request.POST.get('year_built', None)
            lead.square_footage = request.POST.get('square_footage', None)
            lead.current_insurer = request.POST.get('current_insurer', '')
            lead.num_bedrooms = request.POST.get('num_bedrooms', None)
            lead.num_bathrooms = request.POST.get('num_bathrooms', None)
            
        elif insurance_type == 'business':
            lead.business_name = request.POST.get('business_name', '')
            lead.business_address = request.POST.get('business_address', '')
            lead.industry = request.POST.get('industry', '')
            lead.num_employees = request.POST.get('num_employees', None)
            lead.annual_revenue = request.POST.get('annual_revenue', '')
            lead.current_insurer = request.POST.get('current_insurer', '')
        
        # Save the lead
        lead.save()
        
        # Verify ZIP code was saved correctly by retrieving from DB
        fresh_lead = Lead.objects.get(id=lead.id)
        print(f"LEAD FROM DB AFTER SAVE - ZIP CODE: '{fresh_lead.zip_code}'")
        
        # Now perform validation and store results - FORCE THIS TO RUN!
        print("RUNNING VALIDATION FOR NEW LEAD...")
        from lead_validation.utils import validate_and_store_lead_data
        validation_results = validate_and_store_lead_data(lead)
        print(f"VALIDATION COMPLETE. Score: {validation_results['score']}")
        
        # Verify validation was saved
        updated_lead = Lead.objects.get(id=lead.id)
        print(f"After validation - Lead ID: {updated_lead.id}, Score: {updated_lead.validation_score}")
        print(f"Validation details: {updated_lead.validation_details}")
        
        # Increment conversions
        link.increment_conversions()
        
        # Calculate payment based on state
        lead_state = lead.state
        
        try:
            # First try to get a rate for the specific state and insurance type
            payment_rate = PaymentRate.objects.get(
                state=lead_state,
                insurance_type=lead.insurance_type,
                is_active=True
            )
        except PaymentRate.DoesNotExist:
            try:
                # If no state-specific rate, get the nationwide rate for this insurance type
                payment_rate = PaymentRate.objects.get(
                    state='',  # Empty string means nationwide
                    insurance_type=lead.insurance_type,
                    is_active=True
                )
            except PaymentRate.DoesNotExist:
                # If all else fails, use a default rate
                from decimal import Decimal
                payment_amount = Decimal('25.00')
            else:
                payment_amount = payment_rate.rate_amount
        else:
            payment_amount = payment_rate.rate_amount
            
        # Update link earnings
        link.earnings += payment_amount
        link.paid_conversions += 1
        link.save(update_fields=['earnings', 'paid_conversions'])
        
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
        # Validate lead information before creating
        email = request.session.get('email', '')
        phone = request.session.get('phone', '')
        zip_code = request.session.get('zip_code', '')
        state = request.session.get('state', '')
        name = request.session.get('name', '')
        
        # Perform validations
        email_validation = validate_email_address(email)
        phone_validation = validate_phone_number(phone)
        location_validation = validate_location(zip_code, state)
        name_validation = validate_name(name)
        
        # Check if lead passes validation
        validation_issues = []
        if not email_validation['overall']:
            validation_issues.append(f"Email issue: {'Disposable email' if email_validation['is_disposable'] else 'Invalid format'}")
        if not phone_validation['overall']:
            validation_issues.append("Phone issue: Invalid or fake number")
        if not location_validation['valid']:
            validation_issues.append(f"Location issue: {location_validation['issue']}")
        if not name_validation['valid']:
            validation_issues.append(f"Name issue: {name_validation['issue']}")
        
        # If there are validation issues, redirect back with errors
        if validation_issues:
            for issue in validation_issues:
                messages.error(request, issue)
            # Gather all session data for the summary
            form_data = {k: v for k, v in request.session.items() if not k.startswith('_')}
            return render(request, 'lead_capture/step4_confirmation.html', {
                'code': code,
                'insurance_type': insurance_type,
                'form_data': form_data,
                'validation_issues': validation_issues
            })
        
        # Create the lead from session data (passing validation)
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
        
        # Verify validation was saved
        updated_lead = Lead.objects.get(id=lead.id)
        print(f"After validation - Lead ID: {updated_lead.id}, Score: {updated_lead.validation_score}")
        print(f"Validation details: {updated_lead.validation_details}")
        
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
