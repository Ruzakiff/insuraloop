from django.utils import timezone
from .models import ValidationSetting, ValidationLog
from lead_capture.models import Lead
import logging

logger = logging.getLogger(__name__)

def validate_and_store_lead_data(lead):
    """
    Validates lead data and stores results in the lead model
    Returns validation results in standard format
    """
    try:
        # Import validation functions here to avoid circular imports
        from lead_validation.views import validate_email_address, validate_phone_number, validate_location, validate_name
        
        print(f"VALIDATING LEAD: {lead.id} - name={lead.name}, email={lead.email}, zip={lead.zip_code}")
        
        # Perform validations with error handling
        try:
            email_validation = validate_email_address(lead.email)
        except Exception as e:
            logger.error(f"Email validation error: {e}")
            email_validation = {'overall': False, 'format_valid': False, 'is_disposable': False}
            
        try:
            phone_validation = validate_phone_number(lead.phone)
        except Exception as e:
            logger.error(f"Phone validation error: {e}")
            phone_validation = {'overall': False, 'is_valid_format': False, 'is_obvious_fake': False}
            
        try:
            location_validation = validate_location(lead.zip_code)
        except Exception as e:
            logger.error(f"Location validation error: {e}")
            location_validation = {'valid': False, 'issue': 'Validation error'}
            
        try:
            name_validation = validate_name(lead.name)
        except Exception as e:
            logger.error(f"Name validation error: {e}")
            name_validation = {'valid': False, 'issue': 'Validation error'}
        
        # Build validation results dictionary in expected format
        validation_results = {
            'email': email_validation,
            'phone': phone_validation,
            'location': location_validation,
            'name': name_validation
        }
        
        # Calculate score (0 to 100)
        score = 0
        issues = []
        
        # Email validation (25 points)
        if email_validation.get('overall', False):
            score += 25
            print("✓ Email validation passed")
        else:
            print("✗ Email validation failed")
            if not email_validation.get('format_valid', True):
                issues.append("Invalid email format")
            if email_validation.get('is_disposable', False):
                issues.append("Disposable email detected")
        
        # Phone validation (25 points)
        if phone_validation.get('overall', False):
            score += 25
            print("✓ Phone validation passed")
        else:
            print("✗ Phone validation failed")
            if not phone_validation.get('is_valid_format', True):
                issues.append("Invalid phone format")
            if phone_validation.get('is_obvious_fake', False):
                issues.append("Obviously fake phone pattern")
        
        # Location validation (25 points)
        if location_validation.get('valid', False):
            score += 25
            print("✓ Location validation passed")
        else:
            print("✗ Location validation failed")
            if location_validation.get('issue'):
                issues.append(location_validation['issue'])
        
        # Name validation (25 points)
        if name_validation.get('valid', False):
            score += 25
            print("✓ Name validation passed")
        else:
            print("✗ Name validation failed")
            if name_validation.get('issue'):
                issues.append(name_validation['issue'])
        
        print(f"VALIDATION SCORE CALCULATED: {score}")
        
        # Store validation results
        lead.validation_score = score
        lead.validation_details = validation_results
        lead.validation_timestamp = timezone.now()
        
        # Save the results
        lead.save()
        
        # Get assessment and recommendation based on score
        if score < 30:
            assessment = "High Risk"
            recommendation = "Reject"
        elif score < 70:
            assessment = "Medium Risk"
            recommendation = "Review"
        else:
            assessment = "Low Risk"
            recommendation = "Approve"
        
        # Return in original API format
        return {
            'score': score,
            'validations': validation_results,
            'overall_score': score,
            'max_score': 100,
            'issues': issues,
            'assessment': assessment,
            'recommendation': recommendation
        }
    
    except Exception as e:
        logger.error(f"Validation error for lead {lead.id}: {e}")
        # Fallback response
        return {
            'score': 0,
            'validations': {
                'email': {'overall': False},
                'phone': {'overall': False},
                'location': {'valid': False},
                'name': {'valid': False}
            },
            'overall_score': 0,
            'max_score': 100,
            'issues': ["System error during validation"],
            'assessment': "Error",
            'recommendation': "Manual Review Required"
        }

def fix_missing_validations():
    """
    Run this from the Django shell to fix existing leads with missing validation data
    """
    leads_without_validation = Lead.objects.filter(validation_details__isnull=True)
    print(f"Found {leads_without_validation.count()} leads with missing validation")
    
    for lead in leads_without_validation:
        print(f"Validating lead ID {lead.id}: {lead.name}")
        validate_and_store_lead_data(lead)
    
    return f"Validated {leads_without_validation.count()} leads" 