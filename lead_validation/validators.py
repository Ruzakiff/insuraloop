import re
import logging
from django.core.validators import validate_email as django_validate_email
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

def validate_email_address(email):
    """Email validation logic"""
    if not email:
        return {'valid': False, 'issue': "Missing email address"}
    
    # Check basic format
    if '@' not in email or '.' not in email.split('@')[1]:
        return {'valid': False, 'issue': "Invalid email format"}
    
    # Use Django's validator
    try:
        django_validate_email(email)
        django_valid = True
    except ValidationError:
        django_valid = False
        return {'valid': False, 'issue': "Invalid email format"}
    
    # Check for disposable email
    domain = email.split('@')[1]
    disposable_domains = [
        'mailinator.com', 'tempmail.com', 'guerrillamail.com', 'yopmail.com', 
        '10minutemail.com', 'trashmail.com', 'throwawaymail.com', 'fakeinbox.com',
        'temp-mail.org', 'maildrop.cc'
    ]
    
    if domain in disposable_domains:
        return {'valid': False, 'issue': "Disposable email detected"}
    
    return {'valid': True}

def validate_phone_number(phone):
    """Phone number validation logic"""
    if not phone:
        return {'valid': False, 'issue': "Missing phone number"}
    
    # Clean the phone number
    phone = re.sub(r'[^0-9]', '', phone)
    
    # Check length (US numbers)
    is_valid_length = len(phone) in [10, 11]
    if len(phone) == 11 and not phone.startswith('1'):
        is_valid_length = False
    
    if not is_valid_length:
        return {'valid': False, 'issue': "Invalid phone number length"}
    
    # Check for obvious fake patterns
    obvious_fakes = [
        '1234567890', '0987654321', '1111111111', '2222222222', '3333333333',
        '4444444444', '5555555555', '6666666666', '7777777777', '8888888888',
        '9999999999', '0000000000'
    ]
    
    normalized_phone = phone[-10:] if len(phone) >= 10 else phone
    if normalized_phone in obvious_fakes:
        return {'valid': False, 'issue': "Obviously fake phone number"}
    
    return {'valid': True}

def validate_location(zip_code, state=None):
    """Location validation logic"""
    if not zip_code:
        return {'valid': False, 'issue': "Missing ZIP code"}
    
    # Basic US ZIP code validation
    zip_valid = bool(re.match(r'^\d{5}(-\d{4})?$', zip_code))
    if not zip_valid:
        return {'valid': False, 'issue': "Invalid ZIP code format"}
    
    # Could add state validation here if needed
    return {'valid': True}

def validate_name(name):
    """Name validation logic"""
    if not name:
        return {'valid': False, 'issue': "Missing name"}
    
    name = name.strip()
    
    # Check for minimum length
    if len(name) < 2:
        return {'valid': False, 'issue': "Name too short"}
    
    # Check for first and last name
    has_space = ' ' in name.strip()
    if not has_space:
        return {'valid': False, 'issue': "Missing last name"}
    
    return {'valid': True} 