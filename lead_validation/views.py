from rest_framework.decorators import api_view
from rest_framework.response import Response
import re
import requests
import dns.resolver
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from lead_capture.models import Lead
import logging
import string
from collections import Counter

logger = logging.getLogger(__name__)

@api_view(['POST'])
def validate_lead(request):
    """Comprehensive lead validation endpoint"""
    data = request.data
    print("Received data for validation:", data)  # Debug line
    email = data.get('email', '')
    phone = data.get('phone', '')
    zip_code = data.get('zip_code', '')
    state = data.get('state', '')
    name = data.get('name', '')
    
    # Initialize results
    results = {
        'overall_score': 0,
        'max_score': 100,
        'issues': [],
        'validations': {
            'email': validate_email_address(email),
            'phone': validate_phone_number(phone),
            'location': validate_location(zip_code, state),
            'name': validate_name(name)
        }
    }
    
    # Cross-field validations
    cross_validations = validate_cross_fields(email, phone, name, zip_code)
    results['validations']['cross_field'] = cross_validations
    if not cross_validations['consistent']:
        results['issues'].extend(cross_validations['issues'])
    
    # Calculate overall score and collect issues
    score = 0
    
    # Email validation (up to 40 points)
    email_validation = results['validations']['email']
    if not email_validation['format_valid']:
        results['issues'].append("Invalid email format")
        score += 20
    if email_validation['is_disposable']:
        results['issues'].append("Disposable email detected")
        score += 30
    if not email_validation.get('has_mx', True):
        results['issues'].append("Email domain cannot receive mail")
        score += 20
    if email_validation.get('is_suspicious_pattern', False):
        results['issues'].append("Email follows suspicious pattern")
        score += 15
    
    # Phone validation (up to 30 points)
    phone_validation = results['validations']['phone']
    if not phone_validation['is_valid_format']:
        results['issues'].append("Invalid phone format")
        score += 15
    if phone_validation.get('is_obvious_fake', False):
        results['issues'].append("Obviously fake phone pattern")
        score += 30
    if phone_validation.get('suspicious_pattern', False):
        results['issues'].append("Phone has suspicious digit pattern")
        score += 10
    
    # Location validation (up to 15 points)
    location_validation = results['validations']['location']
    if not location_validation['valid']:
        results['issues'].append(location_validation['issue'])
        score += 15
    if location_validation.get('high_risk_area', False):
        results['issues'].append("High-risk geographic location")
        score += 10
        
    # Name validation (up to 15 points)
    name_validation = results['validations']['name']
    if not name_validation['valid']:
        results['issues'].append(name_validation['issue'])
        score += 15
    if name_validation.get('is_suspicious', False):
        results['issues'].append("Name pattern appears suspicious")
        score += 10
    
    # Cap the score at 100
    results['overall_score'] = min(score, 100)
    
    # Overall assessment
    if score < 20:
        results['assessment'] = "Low Risk"
        results['recommendation'] = "Approve"
    elif score < 50:
        results['assessment'] = "Medium Risk"
        results['recommendation'] = "Review"
    else:
        results['assessment'] = "High Risk"
        results['recommendation'] = "Reject"
    
    return Response(results)

def validate_email_address(email):
    """Enhanced email validation with anti-fraud measures"""
    if not email:
        return {'overall': False, 'format_valid': False, 'is_disposable': False, 'is_role_account': False}
    
    # Trim whitespace
    email = email.strip().lower()
    
    # Basic format validation with regex
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    format_valid = bool(re.match(email_regex, email))
    
    # Check for Django's built-in email validation
    try:
        validate_email(email)
        django_valid = True
    except ValidationError:
        django_valid = False
        format_valid = False
    
    # Split email into local part and domain
    if '@' in email:
        local_part, domain = email.split('@', 1)
    else:
        local_part, domain = email, ""
        
    # Enhanced disposable email detection
    # Expanded list of disposable domains
    disposable_domains = [
        'mailinator.com', 'tempmail.com', 'throwaway.com', 'temp-mail.org', 
        'guerrillamail.com', 'yopmail.com', 'getairmail.com', 'getnada.com',
        'mailnesia.com', '10minutemail.com', 'mailinator.net', 'tempmail.net',
        'dispostable.com', 'maildrop.cc', 'fakeinbox.com', 'mailnull.com',
        'trashmail.com', 'spamgourmet.com', 'sharklasers.com', 'fastmail.one'
    ]
    is_disposable = domain in disposable_domains
    
    # Check for mx records if domain validation passed
    has_mx = True  # default to True to avoid penalizing if DNS check fails
    if format_valid and not is_disposable:
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            has_mx = len(mx_records) > 0
        except Exception as e:
            logger.warning(f"MX lookup failed for {domain}: {e}")
    
    # Check for role accounts
    role_prefixes = ['admin@', 'info@', 'support@', 'sales@', 'contact@', 
                     'help@', 'service@', 'noreply@', 'no-reply@', 'webmaster@']
    is_role_account = any(email.startswith(prefix) for prefix in role_prefixes)
    
    # Check for suspicious patterns
    is_suspicious_pattern = False
    
    # Check for keyboard walking (e.g., qwerty, asdfgh)
    keyboard_rows = [
        "qwertyuiop", "asdfghjkl", "zxcvbnm"
    ]
    
    for row in keyboard_rows:
        if any(seq in local_part.lower() for seq in [row[i:i+4] for i in range(len(row)-3)]):
            is_suspicious_pattern = True
    
    # Check for sequential characters (e.g., abcdef, 12345)
    for seq_length in range(4, 10):
        for start in range(len(local_part) - seq_length + 1):
            chunk = local_part[start:start+seq_length].lower()
            # Check for sequential letters
            if all(ord(chunk[i+1]) == ord(chunk[i])+1 for i in range(len(chunk)-1)):
                is_suspicious_pattern = True
            # Check for sequential numbers
            if chunk.isdigit() and all(int(chunk[i+1]) == int(chunk[i])+1 for i in range(len(chunk)-1)):
                is_suspicious_pattern = True
    
    # Check for repeated patterns
    for pattern_len in range(2, 5):
        for i in range(len(local_part) - pattern_len * 2 + 1):
            pattern = local_part[i:i+pattern_len]
            if pattern == local_part[i+pattern_len:i+pattern_len*2]:
                is_suspicious_pattern = True
    
    # Determine overall validity 
    overall = format_valid and django_valid and not is_disposable and has_mx and not is_suspicious_pattern
    
    return {
        'overall': overall,
        'format_valid': format_valid and django_valid,
        'is_disposable': is_disposable,
        'is_role_account': is_role_account,
        'has_mx': has_mx,
        'is_suspicious_pattern': is_suspicious_pattern
    }

def validate_phone_number(phone):
    """Enhanced phone validation with anti-fraud measures"""
    if not phone:
        return {'overall': False, 'is_valid_format': False, 'is_obvious_fake': False}
    
    # Clean the phone number
    phone = re.sub(r'[^0-9]', '', phone)
    
    # Check length (US numbers should be 10 digits, or 11 with country code)
    is_valid_length = len(phone) in [10, 11]
    if len(phone) == 11 and not phone.startswith('1'):
        is_valid_length = False
    
    # Enhanced fake pattern detection
    obvious_fakes = [
        '1234567890', '0987654321', '9876543210', 
        '1111111111', '2222222222', '3333333333', '4444444444',
        '5555555555', '6666666666', '7777777777', '8888888888',
        '9999999999', '0000000000', '1212121212', '1234123412',
        '1122334455', '9988776655', '1231231234', '4565456545'
    ]
    
    # Use normalized 10-digit version for pattern matching
    normalized_phone = phone[-10:] if len(phone) >= 10 else phone
    is_obvious_fake = normalized_phone in obvious_fakes
    
    # Comprehensive area code check (US only)
    invalid_area_codes = [
        '000', '555', '999', '111', '123', '321', '100', '200', '300', 
        '400', '500', '600', '700', '800', '900', '411'
    ]
    
    if len(normalized_phone) >= 3:
        area_code = normalized_phone[:3]
        # More comprehensive invalid area code check
        is_valid_area_code = area_code not in invalid_area_codes and not area_code.endswith('11')
        
        # Check for premium rate/scam area codes
        premium_rate_codes = ['900', '976', '550', '809', '284', '649']
        is_premium_rate = area_code in premium_rate_codes
    else:
        is_valid_area_code = False
        is_premium_rate = False
    
    # Check for suspicious digit patterns
    suspicious_pattern = False
    
    # Check for sequential digits (more than 3 in a row)
    for i in range(len(normalized_phone) - 3):
        if (all(int(normalized_phone[i+j+1]) == int(normalized_phone[i+j])+1 for j in range(3)) or
            all(int(normalized_phone[i+j+1]) == int(normalized_phone[i+j])-1 for j in range(3))):
            suspicious_pattern = True
    
    # Check for repeated digit patterns
    digit_counts = Counter(normalized_phone)
    most_common_digit, count = digit_counts.most_common(1)[0]
    if count >= 6:  # If any digit appears 6 or more times
        suspicious_pattern = True
    
    # Check for palindrome pattern
    if normalized_phone == normalized_phone[::-1] and len(normalized_phone) > 5:
        suspicious_pattern = True
    
    # Determine overall validity
    is_valid_format = is_valid_length and is_valid_area_code and not is_premium_rate
    overall = is_valid_format and not is_obvious_fake and not suspicious_pattern
    
    return {
        'overall': overall,
        'is_valid_format': is_valid_format,
        'is_obvious_fake': is_obvious_fake,
        'suspicious_pattern': suspicious_pattern,
        'is_premium_rate': is_premium_rate if len(normalized_phone) >= 3 else False
    }

def validate_location(zip_code, state=None):
    """Enhanced location validation with fraud detection"""
    result = {
        'valid': False,
        'issue': None,
        'high_risk_area': False
    }
    
    if not zip_code:
        result['issue'] = "Missing ZIP code"
        return result
        
    # Clean the ZIP code
    zip_code = zip_code.strip()
    
    # Basic US ZIP code validation
    if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
        result['issue'] = "Invalid ZIP code format"
        return result
    
    # Extract the 5-digit part
    zip5 = zip_code[:5]
    
    # High risk ZIP codes (example list - would need a complete database in production)
    high_risk_zips = [
        '90001', '33142', '33125', '33126', '33128', '33136', '11208', 
        '11207', '11233', '11236', '10029', '10031', '10032'
    ]
    
    if zip5 in high_risk_zips:
        result['high_risk_area'] = True
    
    # ZIP code to state mapping
    zip_state_map = {
        '0': ['CT', 'MA', 'ME', 'NH', 'NJ', 'PR', 'RI', 'VT'],
        '1': ['DE', 'NY', 'PA'],
        '2': ['DC', 'MD', 'NC', 'SC', 'VA', 'WV'],
        '3': ['AL', 'FL', 'GA', 'MS', 'TN'],
        '4': ['IN', 'KY', 'MI', 'OH'],
        '5': ['IA', 'MN', 'MT', 'ND', 'SD', 'WI'],
        '6': ['IL', 'KS', 'MO', 'NE'],
        '7': ['AR', 'LA', 'OK', 'TX'],
        '8': ['AZ', 'CO', 'ID', 'NM', 'NV', 'UT', 'WY'],
        '9': ['AK', 'CA', 'HI', 'OR', 'WA']
    }
    
    # Derive state from ZIP
    first_digit = zip5[0]
    state_list = zip_state_map.get(first_digit, [])
    
    if state_list:
        result['derived_state'] = state_list[0]  # Default to first state in region
        
        # Check for ZIP-state mismatch if state is provided
        if state and state.upper() not in state_list:
            result['issue'] = f"ZIP code {zip5} is not in state {state}"
            result['zip_state_mismatch'] = True
            return result
    
    # For now, assume all well-formatted ZIPs are valid if no other issues
    result['valid'] = True
    
    return result

def validate_name(name):
    """Enhanced name validation with fraud detection"""
    if not name:
        return {'valid': False, 'issue': 'Name is required', 'is_suspicious': False}
    
    # Trim whitespace
    name = name.strip()
    
    # Check minimum length
    if len(name) < 2:
        return {'valid': False, 'issue': 'Name is too short', 'is_suspicious': True}
    
    # Check for numbers
    if re.search(r'\d', name):
        return {'valid': False, 'issue': 'Name contains numbers', 'is_suspicious': True}
    
    # Check for excessive special characters
    special_char_count = len(re.findall(r'[^a-zA-Z\s\'-]', name))
    if special_char_count > 1:
        return {'valid': False, 'issue': 'Name contains too many special characters', 'is_suspicious': True}
    
    # Split into first/last name
    name_parts = name.split()
    
    # Check for suspicious names
    suspicious = False
    
    # List of obviously fake names
    fake_names = [
        'test', 'testing', 'tester', 'fake', 'fakename', 'anonymous', 'anon',
        'john doe', 'jane doe', 'john smith', 'jsmith', 'mickey mouse', 'donald duck',
        'admin', 'administrator', 'user', 'username', 'asdf', 'qwerty'
    ]
    
    if name.lower() in fake_names or any(part.lower() in fake_names for part in name_parts):
        suspicious = True
    
    # Check for keyboard patterns in name
    keyboard_rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
    for row in keyboard_rows:
        # Check for keyboard patterns of 4+ consecutive keys
        for i in range(len(row) - 3):
            pattern = row[i:i+4]
            if pattern.lower() in name.lower():
                suspicious = True
    
    # Check for excessive repeated characters
    for part in name_parts:
        if part:
            char_counts = Counter(part.lower())
            most_common_char, count = char_counts.most_common(1)[0]
            # If any character is repeated more than half the length of the name part
            if count > max(3, len(part) / 2):
                suspicious = True
    
    # Check for single-character first or last name (unusual in most locales)
    if any(len(part) == 1 for part in name_parts):
        suspicious = True
    
    # Check first and last names are different (if multiple parts)
    if len(name_parts) > 1 and name_parts[0].lower() == name_parts[-1].lower():
        suspicious = True
    
    # Check for celebrity names (common in fake accounts)
    celebrity_names = [
        'michael jackson', 'elvis presley', 'beyonce', 'taylor swift', 'brad pitt',
        'angelina jolie', 'tom cruise', 'jennifer lopez', 'justin bieber', 'lebron james',
        'donald trump', 'barack obama', 'elon musk', 'jeff bezos', 'bill gates'
    ]
    
    if name.lower() in celebrity_names:
        suspicious = True
    
    # Result
    valid = len(name) >= 2 and special_char_count <= 1 and not re.search(r'\d', name)
    
    return {
        'valid': valid,
        'issue': None if valid else 'Invalid name format',
        'is_suspicious': suspicious
    }

def validate_cross_fields(email, phone, name, zip_code):
    """Cross-validate multiple fields to detect inconsistencies"""
    result = {
        'consistent': True,
        'issues': []
    }
    
    # Check for different identities across fields
    if email and name:
        # Extract name from email if possible
        email_name_part = email.split('@')[0].lower() if '@' in email else ''
        
        # Clean the email name part
        email_name_part = re.sub(r'[0-9_.\-+]', '', email_name_part)
        
        # Clean the provided name
        clean_name = re.sub(r'[^a-z]', '', name.lower())
        
        # If email contains a name part, check if it's completely unrelated to provided name
        if email_name_part and len(email_name_part) > 3 and len(clean_name) > 3:
            # Check if either name is a substring of the other or if they share significant substrings
            if (email_name_part not in clean_name and 
                clean_name not in email_name_part and
                not any(part in email_name_part for part in clean_name.split() if len(part) > 3)):
                
                result['consistent'] = False
                result['issues'].append("Name in email doesn't match provided name")
    
    # Add more cross-field validations here as needed
    
    return result

@login_required
def validate_lead(request, lead_id):
    """Manually validate a lead and update its validation data"""
    lead = get_object_or_404(Lead, id=lead_id)
    
    # Check if the current user owns the lead
    if lead.agent != request.user and not request.user.is_staff:
        return JsonResponse({'error': 'You do not have permission to validate this lead'}, status=403)
    
    # Perform the validation
    email_validation = validate_email_address(lead.email)
    phone_validation = validate_phone_number(lead.phone)
    location_validation = validate_location(lead.zip_code)
    name_validation = validate_name(lead.name)
    
    # Build validation results dictionary
    validation_results = {
        'email': email_validation,
        'phone': phone_validation,
        'location': location_validation,
        'name': name_validation
    }
    
    # Calculate score (0 to 100)
    score = 0
    if email_validation.get('overall', False): score += 25
    if phone_validation.get('overall', False): score += 25
    if location_validation.get('valid', False): score += 25
    if name_validation.get('valid', False): score += 25
    
    # Update the lead
    lead.validation_score = score
    lead.validation_details = validation_results
    lead.validation_timestamp = timezone.now()
    lead.save(update_fields=['validation_score', 'validation_details', 'validation_timestamp'])
    
    return JsonResponse({
        'success': True,
        'lead_id': lead.id,
        'score': score,
        'validation_results': validation_results
    })