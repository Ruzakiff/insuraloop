from django.utils import timezone
from .models import ValidationSetting, ValidationLog
from .views import validate_email_address, validate_phone_number, validate_location, validate_name

def validate_and_store_lead_data(lead):
    """
    Validates lead data and stores results in the lead model
    
    Args:
        lead: A Lead model instance
        
    Returns:
        dict: Validation results
    """
    # Get validation configuration
    # config = ValidationSetting.get_active()
    
    # Print for debugging
    print(f"VALIDATING LEAD: name={lead.name}, email={lead.email}, zip={lead.zip_code}")
    
    # Perform validations
    email_validation = validate_email_address(lead.email)
    phone_validation = validate_phone_number(lead.phone)
    location_validation = validate_location(lead.zip_code, lead.state)
    name_validation = validate_name(lead.name)
    
    validation_results = {
        'email': email_validation,
        'phone': phone_validation,
        'location': location_validation,
        'name': name_validation
    }
    
    # Print validation results
    print(f"VALIDATION RESULTS: {validation_results}")
    
    # Calculate a very basic score (0 to 100)
    score = 0
    weight_per_validation = 25  # 25 points for each valid field
    
    if email_validation.get('overall', False):
        score += weight_per_validation
    
    if phone_validation.get('overall', False):
        score += weight_per_validation
    
    if location_validation.get('valid', False):
        score += weight_per_validation
    
    if name_validation.get('valid', False):
        score += weight_per_validation
    
    # Store validation results in the lead
    lead.validation_score = score
    lead.validation_details = validation_results
    lead.validation_timestamp = timezone.now()
    
    # Print final validation data
    print(f"FINAL SCORE: {score}, VALIDATION DETAILS: {validation_results}")
    
    # Save the validation data to the lead
    lead.save(update_fields=['validation_score', 'validation_details', 'validation_timestamp'])
    
    # Log the validation
    ValidationLog.objects.create(
        lead_id=lead.id,
        email=lead.email,
        phone=lead.phone,
        ip_address=lead.ip_address,
        score=score,
        results=validation_results,
        rejection_reason=", ".join(validation_results['issues']) if validation_results.get('issues') else None
    )
    
    return {
        'score': score,
        'validations': validation_results,
        'quality_level': lead.quality_level
    } 