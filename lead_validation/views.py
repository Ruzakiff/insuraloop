from rest_framework.decorators import api_view
from rest_framework.response import Response
import re
import requests
import dns.resolver
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

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
    
    # Calculate overall score and collect issues
    score = 0
    
    # Email validation (up to 40 points)
    email_validation = results['validations']['email']
    if not email_validation['valid_format']:
        results['issues'].append("Invalid email format")
        score += 20
    if email_validation.get('is_disposable', False):
        results['issues'].append("Disposable email detected")
        score += 30
    if not email_validation.get('has_mx', True):
        results['issues'].append("Email domain cannot receive mail")
        score += 20
    
    # Phone validation (up to 30 points)
    phone_validation = results['validations']['phone']
    if not phone_validation['valid_format']:
        results['issues'].append("Invalid phone format")
        score += 15
    if phone_validation.get('is_voip', False):
        results['issues'].append("VoIP number detected")
        score += 10
    if phone_validation.get('is_obvious_fake', False):
        results['issues'].append("Obviously fake phone pattern")
        score += 30
    
    # Location validation (up to 15 points)
    location_validation = results['validations']['location']
    if not location_validation['valid']:
        results['issues'].append(location_validation['issue'])
        score += 15
    
    # Name validation (up to 15 points)
    name_validation = results['validations']['name']
    if not name_validation['valid']:
        results['issues'].append(name_validation['issue'])
        score += 15
    
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
    """Validate email with multiple checks"""
    result = {
        'valid_format': False,
        'is_disposable': False,
        'has_mx': False,
        'is_role_account': False,
        'overall': False
    }
    
    if not email:
        return result
    
    # Check basic format
    try:
        validate_email(email)
        result['valid_format'] = True
    except ValidationError:
        return result
    
    # Check domain
    domain = email.split('@')[-1].lower()
    
    # Check disposable email
    disposable_domains = [
        'mailinator.com', 'tempmail.com', 'fakeinbox.com', 'yopmail.com', 
        'guerrillamail.com', 'sharklasers.com', '10minutemail.com', 
        'getairmail.com', 'mailnesia.com', 'trashmail.com', 'mailnator.com',
        'temp-mail.org', 'throwawaymail.com', 'tempinbox.com'
    ]
    result['is_disposable'] = domain in disposable_domains
    
    # Check MX records
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        result['has_mx'] = bool(mx_records)
    except Exception:
        result['has_mx'] = False
    
    # Check for role-based account
    role_accounts = ['admin', 'webmaster', 'info', 'support', 'contact', 'sales', 'help']
    local_part = email.split('@')[0].lower()
    result['is_role_account'] = local_part in role_accounts
    
    # Overall assessment
    result['overall'] = (
        result['valid_format'] and 
        result['has_mx'] and 
        not result['is_disposable'] and 
        not result['is_role_account']
    )
    
    return result

def validate_phone_number(phone):
    """Validate phone number format and patterns"""
    result = {
        'valid_format': False,
        'is_obvious_fake': False,
        'overall': False
    }
    
    if not phone:
        return result
    
    # Remove non-digits
    digits = re.sub(r'\D', '', phone)
    
    # Basic length check
    if 10 <= len(digits) <= 15:
        result['valid_format'] = True
    
    # Check for fake patterns
    fake_patterns = [
        '1234567890', '0000000000', '1111111111', '2222222222',
        '3333333333', '4444444444', '5555555555', '6666666666',
        '7777777777', '8888888888', '9999999999'
    ]
    result['is_obvious_fake'] = digits in fake_patterns or len(set(digits)) <= 2
    
    # Overall assessment
    result['overall'] = result['valid_format'] and not result['is_obvious_fake']
    
    return result

def validate_location(zip_code, state=None):
    """Validate location data and derive state from ZIP if needed"""
    result = {
        'valid': True,
        'issue': None
    }
    
    if not zip_code:
        result['valid'] = False
        result['issue'] = "Missing ZIP code"
        return result
        
    # Clean the ZIP code
    zip_code = zip_code.strip()
    
    # Basic US ZIP code validation
    if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
        result['valid'] = False
        result['issue'] = "Invalid ZIP code format"
        return result
    
    # If state is not provided, derive it from ZIP code
    if not state:
        # ZIP code to state mapping (first digits)
        zip_ranges = {
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
        first_digit = zip_code[0]
        state_list = zip_ranges.get(first_digit)
        
        if state_list:
            # For validation purposes, assume ZIP code is valid if we can map it to potential states
            result['valid'] = True
            # Take the first state in the list as a default (you could use a more precise mapping)
            result['derived_state'] = state_list[0]
        else:
            # This should rarely happen since the ranges cover all possible first digits
            result['valid'] = False
            result['issue'] = "Could not determine state from ZIP code"
    
    return result

def validate_name(name):
    """Basic name validation"""
    result = {
        'valid': False,
        'issue': None
    }
    
    if not name:
        result['issue'] = "Missing name"
        return result
    
    if len(name) < 3:
        result['issue'] = "Name too short"
        return result
    
    # Check for fake/test names
    fake_names = ['test', 'testuser', 'user', 'asdf', 'qwerty', 'testing']
    if name.lower() in fake_names:
        result['issue'] = "Obvious test name"
        return result
    
    # Check if name has both first and last name
    if ' ' not in name:
        result['issue'] = "Missing first or last name"
        return result
    
    result['valid'] = True
    return result