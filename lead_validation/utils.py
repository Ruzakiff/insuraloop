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
def check_for_duplicate_lead(lead_data):
    """
    Check if a lead already exists with similar information
    Returns (is_duplicate, confidence_score, matching_leads, matching_fields)
    """
    from lead_capture.models import Lead
    import logging
    logger = logging.getLogger(__name__)
    
    print(f"Checking for duplicates with data: {lead_data['email']}")
    
    # Look for exact email match first (highest confidence)
    email_matches = Lead.objects.filter(email__iexact=lead_data['email'])
    if email_matches.exists():
        print(f"Found exact email match: {lead_data['email']}")
        return True, 95, email_matches, ["email"]
    
    # Look for exact phone match (high confidence)
    if lead_data.get('phone'):
        # Normalize phone number for comparison
        phone = ''.join(filter(str.isdigit, lead_data['phone']))
        if phone:
            phone_matches = Lead.objects.filter(phone__endswith=phone[-10:])
            if phone_matches.exists():
                print(f"Found phone match: {phone}")
                return True, 90, phone_matches, ["phone"]
    
    # Look for name + zip code match (medium confidence)
    if lead_data.get('name') and lead_data.get('zip_code'):
        name_zip_matches = Lead.objects.filter(
            name__iexact=lead_data['name'],
            zip_code=lead_data['zip_code']
        )
        if name_zip_matches.exists():
            print(f"Found name+zip match: {lead_data['name']} in {lead_data['zip_code']}")
            return True, 75, name_zip_matches, ["name", "zip_code"]
    
    # No duplicates found
    return False, 0, [], []
def validate_and_store_lead_data(lead, save_to_db=True):
    """
    Main validation workflow with hybrid scoring approach
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
    
    # Initialize validation results
    validation_results = {}
    
    # STEP 1: Check for duplicates
    is_duplicate = False
    dup_confidence = 0
    matching_leads = []
    
    print("Checking for duplicates...")
    
    # Only skip duplicate check if we're revalidating an existing lead with ID
    is_revalidation = getattr(lead, '_revalidation', False)
    
    if not is_revalidation:
        is_duplicate, dup_confidence, matching_leads, matching_fields = check_for_duplicate_lead(lead_data)
        
        # If this is an existing lead, filter out self-matches
        if hasattr(lead, 'id') and lead.id is not None:
            matching_leads = [l for l in matching_leads if l.id != lead.id]
            # If all matches were self, it's not a duplicate
            if not matching_leads:
                is_duplicate = False
                dup_confidence = 0
        
        if is_duplicate:
            print(f"DUPLICATE DETECTED! Confidence: {dup_confidence}%")
            # Store matching lead IDs
            matching_lead_ids = [l.id for l in matching_leads]
            validation_results['duplicate_check'] = {
                'is_duplicate': True,
                'confidence': dup_confidence,
                'matching_lead_ids': matching_lead_ids,
                'matching_fields': matching_fields
            }
        else:
            validation_results['duplicate_check'] = {
                'is_duplicate': False
            }
    else:
        print("Skipping duplicate check for revalidation")
        validation_results['duplicate_check'] = {
            'is_duplicate': False,
            'note': 'Skipped for revalidation'
        }
    
    # STEP 2: For lower-confidence duplicates or non-duplicates, continue with AI validation
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
            base_score = 100 - ai_assessment.get('risk_score', 50)
            ai_successful = True
        else:
            logger.info("AI validation failed or low confidence, falling back to rules")
            ai_successful = False
    except Exception as e:
        logger.error(f"Error during AI validation: {e}")
        print(f"AI VALIDATION ERROR: {e}")
        ai_successful = False
        validation_results['ai_assessment'] = {"error": str(e)}
    
    # STEP 3: If AI validation wasn't successful, use rule-based validation
    if not ai_successful:
        # Perform standard validations
        email_result = validate_email_address(lead.email)
        phone_result = validate_phone_number(lead.phone)
        location_result = validate_location(lead.zip_code)
        name_result = validate_name(lead.name)
        
        # Perform cross-field validation
        cross_result = validate_cross_fields(
            lead.email, lead.phone, lead.name, lead.zip_code, 
            getattr(lead, 'ip_address', None)
        )
        
        # Store results
        validation_results.update({
            'email': email_result,
            'phone': phone_result,
            'location': location_result,
            'name': name_result,
            'cross_validation': cross_result
        })
        
        # Calculate base score (0-100)
        base_score = 0
        base_score += 20 if email_result.get('valid', False) else 0
        base_score += 20 if phone_result.get('valid', False) else 0
        base_score += 20 if location_result.get('valid', False) else 0
        base_score += 20 if name_result.get('valid', False) else 0
        base_score += 20 if cross_result.get('consistent', True) else 0
        
        # Apply penalties for suspicious patterns
        if email_result.get('suspicious_pattern', False) or email_result.get('high_risk_tld', False):
            base_score -= 10
        if phone_result.get('suspicious_pattern', False) or phone_result.get('high_risk_area_code', False):
            base_score -= 10
        if location_result.get('high_risk_zip', False):
            base_score -= 10
        if name_result.get('suspicious_pattern', False) or name_result.get('fake_name', False):
            base_score -= 15
        if not cross_result.get('consistent', True):
            base_score -= 15
    
    # STEP 4: Calculate final score incorporating duplicate detection results
    # For lower-confidence duplicates, apply a weighted penalty
    if is_duplicate:
        # Calculate duplicate penalty - much more severe than before
        # For medium confidence (50%), reduce score by 50%
        # For higher confidence (70%), reduce by 70%, etc.
        duplicate_factor = min(0.95, dup_confidence / 100)  # Cap at 95% reduction
        final_score = int(base_score * (1 - duplicate_factor))
        
        validation_results['score_breakdown'] = {
            'base_score': base_score,
            'duplicate_confidence': dup_confidence,
            'duplicate_factor': f"Reducing score by {int(duplicate_factor * 100)}%",
            'final_score': final_score,
            'reason': 'Score reduced due to duplicate detection',
            'is_duplicate': True  # Add this flag explicitly
        }
    else:
        final_score = base_score
        validation_results['score_breakdown'] = {
            'base_score': base_score,
            'final_score': final_score,
            'reason': 'No duplicates detected',
            'is_duplicate': False  # Add this flag explicitly
        }
    
    # Ensure score stays within bounds
    final_score = max(0, min(100, final_score))
    
    print(f"FINAL VALIDATION SCORE: {final_score}/100")
    if is_duplicate:
        print(f"  Base Score: {base_score}")
        print(f"  Duplicate Confidence: {dup_confidence}%")
        print(f"  Reduced by: {int(dup_confidence)}%")
    else:
        print(f"  Base Score: {base_score}")
        print(f"  No duplicates detected")
    
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
def validate_and_store_lead_data(lead, save_to_db=True):
    """
    Main validation workflow with hybrid scoring approach:
    1. Check for duplicates first
    2. Run AI validation 
    3. Fall back to rule-based validation if needed
    4. Calculate final score using hybrid approach that prioritizes duplicates
    
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
    
    # Initialize validation results
    validation_results = {}
    
    # STEP 1: Check for duplicates (except for existing leads being revalidated)
    is_new_lead = not hasattr(lead, 'id') or lead.id is None
    is_duplicate = False
    dup_confidence = 0
    matching_leads = []
    
    if is_new_lead:
        print("Checking for duplicates...")
        is_duplicate, dup_confidence, matching_leads, matching_fields = check_for_duplicate_lead(lead_data)
        
        if is_duplicate:
            print(f"DUPLICATE DETECTED! Confidence: {dup_confidence}%")
            validation_results['duplicate_check'] = {
                'is_duplicate': True,
                'confidence': dup_confidence,
                'matching_lead_ids': [l.id for l in matching_leads],
                'matching_fields': matching_fields
            }
        else:
            validation_results['duplicate_check'] = {
                'is_duplicate': False
            }
    
    # STEP 2: Run AI validation
    ai_result = None
    try:
        logger.info("Attempting AI validation")
        print("\n*** CALLING AI VALIDATOR ***\n")
        
        ai_assessment = analyze_lead_with_ai(lead_data)
        validation_results['ai_assessment'] = ai_assessment
        print(f"AI RESULT: {ai_assessment}")
        
        # If AI validation succeeded with good confidence
        if 'error' not in ai_assessment and ai_assessment.get('confidence', 0) > 50:
            logger.info(f"Using AI validation with confidence: {ai_assessment.get('confidence')}")
            ai_result = ai_assessment
            ai_successful = True
        else:
            logger.info("AI validation failed or low confidence, falling back to rules")
            ai_successful = False
    except Exception as e:
        logger.error(f"Error during AI validation: {e}")
        print(f"AI VALIDATION ERROR: {e}")
        ai_successful = False
        validation_results['ai_assessment'] = {"error": str(e)}
    
    # STEP 3: If AI validation wasn't successful, use rule-based validation
    rule_based_result = None
    if not ai_successful:
        # Perform standard validations
        email_result = validate_email_address(lead.email)
        phone_result = validate_phone_number(lead.phone)
        location_result = validate_location(lead.zip_code)
        name_result = validate_name(lead.name)
        
        # Perform cross-field validation
        cross_result = validate_cross_fields(
            lead.email, lead.phone, lead.name, lead.zip_code, 
            getattr(lead, 'ip_address', None)
        )
        
        # Store results
        rule_based_validations = {
            'email': email_result,
            'phone': phone_result,
            'location': location_result,
            'name': name_result,
            'cross_validation': cross_result
        }
        validation_results.update(rule_based_validations)
        
        # Calculate base score (0-100)
        quality_score = 0
        quality_score += 20 if email_result.get('valid', False) else 0
        quality_score += 20 if phone_result.get('valid', False) else 0
        quality_score += 20 if location_result.get('valid', False) else 0
        quality_score += 20 if name_result.get('valid', False) else 0
        quality_score += 20 if cross_result.get('consistent', True) else 0
        
        # Apply penalties for suspicious patterns
        if email_result.get('suspicious_pattern', False) or email_result.get('high_risk_tld', False):
            quality_score -= 10
        if phone_result.get('suspicious_pattern', False) or phone_result.get('high_risk_area_code', False):
            quality_score -= 10
        if location_result.get('high_risk_zip', False):
            quality_score -= 10
        if name_result.get('suspicious_pattern', False) or name_result.get('fake_name', False):
            quality_score -= 15
        if not cross_result.get('consistent', True):
            quality_score -= 15
            
        # Store the calculated quality score
        rule_based_result = {
            'calculated_score': max(0, min(100, quality_score)),
            'validations': rule_based_validations
        }
    
    # STEP 4: Calculate final score using our hybrid approach
    duplicate_result = (is_duplicate, dup_confidence, matching_leads)
    final_score, score_explanation = calculate_final_score(
        lead_data, 
        duplicate_result,
        ai_result,
        rule_based_result
    )
    
    # Store score breakdown
    validation_results['score_breakdown'] = {
        'final_score': final_score,
        'explanation': score_explanation,
        'is_duplicate': is_duplicate,
        'duplicate_confidence': dup_confidence if is_duplicate else 0
    }
    
    print(f"FINAL VALIDATION SCORE: {final_score}/100")
    print(f"  Explanation: {score_explanation}")
    logger.info(f"Validation complete - Final Score: {final_score}/100")
    
    # Store validation results in lead
   # In the validate_and_store_lead_data function, update this section:

    # Store validation results in lead
    if save_to_db and hasattr(lead, 'id'):
        try:
            lead.validation_score = final_score
            lead.validation_details = validation_results
            lead.validation_timestamp = timezone.now()
            lead.save(update_fields=['validation_score', 'validation_details', 'validation_timestamp'])
            
            # Create validation log - use correct field name
            ValidationLog.objects.create(
                lead=lead,
                score=final_score,
                details=validation_results
                # Don't specify created_at, it will be added automatically
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