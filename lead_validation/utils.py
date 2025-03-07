import logging
from django.utils import timezone
from .models import ValidationLog
from .validators import validate_email_address, validate_phone_number, validate_location, validate_name
from .ai_validator import analyze_lead_with_ai

logger = logging.getLogger(__name__)

def validate_and_store_lead_data(lead, save_to_db=True):
    """
    Main validation workflow:
    1. Try AI validation first
    2. Fall back to rule-based validation if needed
    3. Store results and return assessment
    
    Args:
        lead: Lead object to validate
        save_to_db: Whether to save validation results to database
    """
    logger.info(f"Starting validation for lead data: {lead.email}")
    print(f"VALIDATING LEAD: {getattr(lead, 'id', 'New')} - name={lead.name}, email={lead.email}")
    
    # Prepare lead data for validation
    lead_data = {
        'name': lead.name,
        'email': lead.email,
        'phone': lead.phone,
        'zip_code': lead.zip_code,
        'state': getattr(lead, 'state', ''),
        'address': getattr(lead, 'address', ''),
        'ip_address': getattr(lead, 'ip_address', ''),
        'user_agent': getattr(lead, 'user_agent', '')
    }
    
    # First, try AI validation
    validation_results = {}
    try:
        logger.info("Attempting AI validation")
        print("\n*** CALLING AI VALIDATOR ***\n")
        
        ai_assessment = analyze_lead_with_ai(lead_data)
        validation_results['ai_assessment'] = ai_assessment
        print(f"AI RESULT: {ai_assessment}")
        
        # If AI validation succeeded with good confidence
        if 'error' not in ai_assessment and ai_assessment.get('confidence', 0) > 50:
            logger.info(f"Using AI validation with confidence: {ai_assessment.get('confidence')}")
            # AI returns risk score (higher = worse)
            # We need to invert for our system (higher = better)
            score = 100 - ai_assessment.get('risk_score', 50)
            ai_successful = True
        else:
            logger.info("AI validation failed or low confidence, falling back to rules")
            ai_successful = False
    except Exception as e:
        logger.error(f"Error during AI validation: {e}")
        print(f"AI VALIDATION ERROR: {e}")
        ai_successful = False
        validation_results['ai_assessment'] = {"error": str(e)}
    
    # If AI validation wasn't successful, use rule-based validation
    if not ai_successful:
        # Perform standard validations
        email_result = validate_email_address(lead.email)
        phone_result = validate_phone_number(lead.phone)
        location_result = validate_location(lead.zip_code)
        name_result = validate_name(lead.name)
        
        # Store results
        validation_results.update({
            'email': email_result,
            'phone': phone_result,
            'location': location_result,
            'name': name_result
        })
        
        # Calculate score (0-100)
        score = 0
        score += 25 if email_result.get('valid', False) else 0
        score += 25 if phone_result.get('valid', False) else 0
        score += 25 if location_result.get('valid', False) else 0
        score += 25 if name_result.get('valid', False) else 0
    
    print(f"FINAL VALIDATION SCORE: {score}/100")
    logger.info(f"Validation complete - Score: {score}/100")
    
    # Store validation results in lead
    if save_to_db and hasattr(lead, 'id'):
        try:
            lead.validation_score = score
            lead.validation_details = validation_results
            lead.validation_timestamp = timezone.now()
            lead.save(update_fields=['validation_score', 'validation_details', 'validation_timestamp'])
            
            # Create validation log
            ValidationLog.objects.create(
                lead=lead,
                score=score,
                details=validation_results
            )
            
            logger.info(f"Validation data saved for lead ID: {lead.id}")
        except Exception as e:
            logger.error(f"Error saving validation data: {e}")
            print(f"ERROR SAVING VALIDATION: {e}")
    
    # Return validation results
    return {
        'score': score,
        'validation_results': validation_results,
        'lead_id': getattr(lead, 'id', None)
    }

def fix_missing_validations():
    """Utility function to fix existing leads with missing validation data"""
    from lead_capture.models import Lead
    
    leads_without_validation = Lead.objects.filter(validation_details__isnull=True)
    count = leads_without_validation.count()
    logger.info(f"Found {count} leads with missing validation")
    
    for lead in leads_without_validation:
        logger.info(f"Validating lead ID {lead.id}: {lead.name}")
        validate_and_store_lead_data(lead)
    
    return f"Validated {count} leads"