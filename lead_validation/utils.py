import logging
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import MultipleObjectsReturned
from .models import ValidationLog
from .validators import validate_email_address, validate_phone_number, validate_location, validate_name, validate_cross_fields
from .ai_validator import analyze_lead_with_ai
from lead_capture.models import Lead
import re
from fuzzywuzzy import fuzz

logger = logging.getLogger(__name__)

def check_for_duplicate_lead(lead_data, exclude_id=None):
    """
    Check if a lead already exists with similar information
    Returns (is_duplicate, confidence_score, matching_leads, matching_fields)
    
    Parameters:
    - lead_data: Dictionary with lead information
    - exclude_id: Optional lead ID to exclude from the check (for revalidation)
    """
    from lead_capture.models import Lead
    import logging
    logger = logging.getLogger(__name__)
    
    print(f"Checking for duplicates with data: {lead_data['email']}")
    if exclude_id:
        print(f"Excluding lead ID {exclude_id} from duplicate check (revalidation)")
    
    # Look for exact email match first (highest confidence)
    email_query = Lead.objects.filter(email__iexact=lead_data['email'])
    if exclude_id:
        email_query = email_query.exclude(id=exclude_id)
    
    email_matches = email_query.all()
    if email_matches.exists():
        print(f"Found exact email match: {lead_data['email']}")
        return True, 95, email_matches, ["email"]
    
    # Look for exact phone match (high confidence)
    if lead_data.get('phone'):
        # Normalize phone number for comparison
        phone = ''.join(filter(str.isdigit, lead_data['phone']))
        if phone:
            phone_query = Lead.objects.filter(phone__endswith=phone[-10:])
            if exclude_id:
                phone_query = phone_query.exclude(id=exclude_id)
                
            phone_matches = phone_query.all()
            if phone_matches.exists():
                print(f"Found phone match: {phone}")
                return True, 90, phone_matches, ["phone"]
    
    # Look for name + zip code match (medium confidence)
    if lead_data.get('name') and lead_data.get('zip_code'):
        name_zip_query = Lead.objects.filter(
            name__iexact=lead_data['name'],
            zip_code=lead_data['zip_code']
        )
        if exclude_id:
            name_zip_query = name_zip_query.exclude(id=exclude_id)
            
        name_zip_matches = name_zip_query.all()
        if name_zip_matches.exists():
            print(f"Found name+zip match: {lead_data['name']} in {lead_data['zip_code']}")
            return True, 75, name_zip_matches, ["name", "zip_code"]
    
    # No duplicates found
    return False, 0, [], []

def validate_and_store_lead_data(lead, save_to_db=True):
    """
    Main validation workflow with hybrid scoring approach:
    1. Check for duplicates first
    2. Use AI validation for lead quality assessment 
    3. Calculate final score considering both factors
    """
    logger.info(f"Starting validation for lead data: {lead.email}")
    print(f"VALIDATING LEAD: {getattr(lead, 'id', 'New')} - name={lead.name}, email={lead.email}")
    
    # Prepare lead data for validation
    lead_data = {
        # Basic information
        'name': lead.name,
        'email': lead.email,
        'phone': lead.phone,
        'zip_code': lead.zip_code,
        'state': getattr(lead, 'state', ''),
        'address': getattr(lead, 'address', ''),
        'ip_address': getattr(lead, 'ip_address', ''),
        'user_agent': getattr(lead, 'user_agent', ''),
        
        # Critical field: insurance type
        'insurance_type': lead.insurance_type,
        
        # Additional fields based on insurance type
        'date_of_birth': getattr(lead, 'date_of_birth', ''),
        'preferred_contact_method': getattr(lead, 'preferred_contact_method', ''),
        'preferred_time': getattr(lead, 'preferred_time', ''),
        'notes': getattr(lead, 'notes', ''),
        
        # Auto insurance fields
        'vehicle_vin': getattr(lead, 'vehicle_vin', ''),
        'vehicle_year': getattr(lead, 'vehicle_year', ''),
        'vehicle_make': getattr(lead, 'vehicle_make', ''),
        'vehicle_model': getattr(lead, 'vehicle_model', ''),
        'vehicle_usage': getattr(lead, 'vehicle_usage', ''),
        'annual_mileage': getattr(lead, 'annual_mileage', ''),
        'current_insurer': getattr(lead, 'current_insurer', ''),
        
        # Home insurance fields
        'property_type': getattr(lead, 'property_type', ''),
        'ownership_status': getattr(lead, 'ownership_status', ''),
        'year_built': getattr(lead, 'year_built', ''),
        'square_footage': getattr(lead, 'square_footage', ''),
        
        # Business insurance fields
        'business_name': getattr(lead, 'business_name', ''),
        'industry': getattr(lead, 'industry', ''),
        'num_employees': getattr(lead, 'num_employees', ''),
        'annual_revenue': getattr(lead, 'annual_revenue', '')
    }
    
    print(f"Lead data for validation: insurance_type={lead_data['insurance_type']}, keys={list(lead_data.keys())}")
    
    # Initialize validation results
    validation_results = {}
    
    # STEP 1: Check for duplicates in database
    print("STEP 1: Checking for duplicates in database...")
    
    # Get the lead ID if it exists (for revalidation)
    lead_id = getattr(lead, 'id', None)
    
    # Always perform the duplicate check, excluding self for existing leads
    is_duplicate, dup_confidence, matching_leads, matching_fields = check_for_duplicate_lead(
        lead_data, 
        exclude_id=lead_id  # This will exclude the current lead from the check
    )
    
    if is_duplicate:
        print(f"DATABASE DUPLICATE DETECTED! Confidence: {dup_confidence}%")
        print(f"Matching leads: {[l.id for l in matching_leads]}")
        print(f"Matching fields: {matching_fields}")
        
        # Store matching lead IDs
        matching_lead_ids = [l.id for l in matching_leads]
        validation_results['duplicate_check'] = {
            'is_duplicate': True,
            'confidence': dup_confidence,
            'matching_lead_ids': matching_lead_ids,
            'matching_fields': matching_fields
        }
    else:
        print("No duplicates found in database")
        validation_results['duplicate_check'] = {
            'is_duplicate': False
        }
    
    # STEP 2: Always use AI validation (no fallback to rules)
    try:
        logger.info("STEP 2: Running AI validation")
        print("\n*** CALLING AI VALIDATOR ***\n")
        
        ai_assessment = analyze_lead_with_ai(lead_data)
        validation_results['ai_assessment'] = ai_assessment
        print(f"AI RESULT RECEIVED")
        
        # AI returns risk score (higher = worse)
        # We need to invert for our system (higher = better)
        quality_score = 100 - ai_assessment.get('risk_score', 50)
        print(f"AI risk score: {ai_assessment.get('risk_score', 50)}, converted quality score: {quality_score}")
        
    except Exception as e:
        logger.error(f"Error during AI validation: {e}")
        print(f"AI VALIDATION ERROR: {e}")
        validation_results['ai_assessment'] = {
            "error": str(e),
            "risk_score": 50,  # Neutral score when AI fails
            "issues": ["AI validation error: " + str(e)],
            "assessment": "medium_risk",
            "confidence": 0
        }
        quality_score = 50  # Neutral score in case of error
    
    # STEP 3: Calculate final score considering duplicate detection
    print("STEP 3: Calculating final score based on AI quality and duplicate status")
    if is_duplicate:
        # HIGH CONFIDENCE DUPLICATE (>80%)
        if dup_confidence > 80:
            final_score = max(5, int(quality_score * 0.1))  # 90% reduction, min score 5
            explanation = f"High-confidence duplicate ({dup_confidence}%). AI quality score of {quality_score} reduced by 90%."
        
        # MEDIUM CONFIDENCE DUPLICATE (50-80%)
        elif dup_confidence > 50:
            final_score = max(10, int(quality_score * 0.25))  # 75% reduction, min score 10
            explanation = f"Medium-confidence duplicate ({dup_confidence}%). AI quality score of {quality_score} reduced by 75%."
        
        # LOW CONFIDENCE DUPLICATE (<50%)
        else:
            final_score = max(20, int(quality_score * 0.5))  # 50% reduction, min score 20
            explanation = f"Low-confidence duplicate ({dup_confidence}%). AI quality score of {quality_score} reduced by 50%."
    else:
        # Not a duplicate - use quality score directly
        final_score = quality_score
        explanation = f"No duplicate detected. Using AI quality score of {quality_score}."
    
    # Store score breakdown
    validation_results['score_breakdown'] = {
        'final_score': final_score,
        'explanation': explanation,
        'is_duplicate': is_duplicate,
        'duplicate_confidence': dup_confidence if is_duplicate else 0
    }
    
    print(f"FINAL VALIDATION SCORE: {final_score}/100")
    print(f"  Explanation: {explanation}")
    logger.info(f"Validation complete - Final Score: {final_score}/100")
    
    # Store validation results in lead
    if save_to_db and hasattr(lead, 'id'):
        try:
            lead.validation_score = final_score
            lead.validation_details = validation_results
            lead.validation_timestamp = timezone.now()
            lead.save(update_fields=['validation_score', 'validation_details', 'validation_timestamp'])
            
            # Create validation log
            ValidationLog.objects.create(
                lead=lead,
                score=final_score,
                details=validation_results
            )
            
            logger.info(f"Validation data saved for lead ID: {lead.id}")
        except Exception as e:
            logger.error(f"Error saving validation data: {e}")
            print(f"ERROR SAVING VALIDATION: {e}")
    
    # Return validation results
    return {
        'score': final_score,
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

def calculate_final_score(lead_data, duplicate_result, ai_result, rule_based_result=None):
    """
    Calculate final score using a hybrid approach that prioritizes duplicate detection
    
    Args:
        lead_data: Dictionary of lead data
        duplicate_result: (is_duplicate, confidence, matches)
        ai_result: AI validation result dict
        rule_based_result: Rule-based validation results (optional)
    
    Returns:
        final_score, explanation
    """
    is_duplicate, dup_confidence, matching_leads = duplicate_result
    
    # Get base quality score from AI or rules
    if ai_result and 'risk_score' in ai_result:
        # AI risk score is 0-100 where higher is worse
        # Convert to quality score where higher is better
        quality_score = 100 - ai_result.get('risk_score', 50)
        score_source = "AI"
    elif rule_based_result:
        # Calculate from rule-based validation
        quality_score = rule_based_result.get('calculated_score', 50)
        score_source = "rule-based validation"
    else:
        quality_score = 50  # Default middle score
        score_source = "default"
    
    # Calculate duplicate impact
    if is_duplicate:
        # HIGH CONFIDENCE DUPLICATE (>80%)
        if dup_confidence > 80:
            final_score = max(5, int(quality_score * 0.1))  # 90% reduction, min score 5
            explanation = f"High-confidence duplicate ({dup_confidence}%). Quality score of {quality_score} reduced by 90%."
        
        # MEDIUM CONFIDENCE DUPLICATE (50-80%)
        elif dup_confidence > 50:
            final_score = max(10, int(quality_score * 0.25))  # 75% reduction, min score 10
            explanation = f"Medium-confidence duplicate ({dup_confidence}%). Quality score of {quality_score} reduced by 75%."
        
        # LOW CONFIDENCE DUPLICATE (<50%)
        else:
            final_score = max(20, int(quality_score * 0.5))  # 50% reduction, min score 20
            explanation = f"Low-confidence duplicate ({dup_confidence}%). Quality score of {quality_score} reduced by 50%."
    else:
        # Not a duplicate - use quality score directly
        final_score = quality_score
        explanation = f"No duplicate detected. Using {score_source} quality score of {quality_score}."
    
    return final_score, explanation
