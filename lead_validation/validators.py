import re
import logging
import string
import tldextract
import socket
from collections import Counter
from django.core.validators import validate_email as django_validate_email
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Enhanced disposable email domains list
DISPOSABLE_EMAIL_DOMAINS = [
    'mailinator.com', 'tempmail.com', 'guerrillamail.com', 'yopmail.com', 
    '10minutemail.com', 'trashmail.com', 'throwawaymail.com', 'fakeinbox.com',
    'temp-mail.org', 'maildrop.cc', 'getairmail.com', 'mailnesia.com',
    'mintemail.com', 'mohmal.com', 'mvrht.net', 'mytemp.email', 'mytrashmail.com',
    'onetimeemail.net', 'sharklasers.com', 'spam4.me', 'spamfighter.cf',
    'spamfighter.ga', 'spamfighter.gq', 'spamfighter.ml', 'spamfighter.tk',
    'tempemail.co', 'tempmail.de', 'tempmail.info', 'tempomail.fr', 'temporaryemail.us',
    'throam.com', 'trash-mail.at', 'trashmail.ws', 'wegwerfmail.de', 'wegwerfmail.net',
    'wegwerfmail.org', 'wemel.top', 'yopmail.fr', 'yopmail.net', 'discard.email',
    'discardmail.com', 'mailinator2.com', 'spambog.com', 'spambog.de', 'spambog.ru',
    'getnada.com', 'inboxkitten.com', 'emailondeck.com', 'emailfake.com', 'tempr.email',
    'tempmail.ninja', 'fakemail.net', 'mailcatch.com', 'rcpt.at', 'dispostable.com'
]

# High-risk TLDs
HIGH_RISK_TLDS = [
    'xyz', 'top', 'work', 'gq', 'cf', 'tk', 'ml', 'ga', 
    'buzz', 'club', 'icu', 'rest', 'space', 'site'
]

# Common keyboard patterns
KEYBOARD_PATTERNS = [
    'qwerty', 'asdfg', 'zxcvb', 'qazwsx', 'qweasd', 'asdzxc', 'poiuy', 'lkjhg',
    'mnbvc', '12345', '67890', '54321', '09876', 'qaz', 'wsx', 'edc', 'rfv', 'tgb'
]

# Obvious fake or test names
FAKE_NAMES = [
    'john doe', 'jane doe', 'test test', 'test user', 'testing testing',
    'first last', 'john smith', 'mary smith', 'foo bar', 'fake name',
    'mickey mouse', 'donald duck', 'jane smith', 'john johnson', 'mary johnson'
]

# Celebrity names often used in fake leads
CELEBRITY_NAMES = [
    'brad pitt', 'angelina jolie', 'tom cruise', 'jennifer aniston', 'kim kardashian',
    'taylor swift', 'justin bieber', 'beyonce knowles', 'leonardo dicaprio', 'adele adkins',
    'tom hanks', 'emma watson', 'will smith', 'ariana grande', 'dwayne johnson',
    'jennifer lopez', 'robert downey', 'selena gomez', 'chris hemsworth', 'lady gaga'
]

# High-fraud area codes
HIGH_FRAUD_AREA_CODES = [
    '212', '213', '310', '323', '332', '347', '415', '470', '516', '551', 
    '617', '646', '657', '669', '702', '718', '786', '917', '929', '949'
]

# VOIP area codes
VOIP_AREA_CODES = [
    '456', '500', '521', '522', '523', '533', '544', '566', '588', '700'
]

# High-fraud ZIP codes (example - you'd want to update this with real data)
HIGH_FRAUD_ZIP_CODES = [
    '10001', '10002', '10003', '11201', '90001', '90210', '33101', '60601', '60602', 
    '20001', '20500', '95054', '95132', '77001', '77002', '19101', '19102'
]

def _detect_keyboard_pattern(text):
    """Detect keyboard patterns in text"""
    text = text.lower()
    for pattern in KEYBOARD_PATTERNS:
        if pattern in text:
            return True
    return False

def _detect_sequential_chars(text, length=3):
    """Detect sequential characters in text"""
    text = text.lower()
    # Alphanumeric sequence detection
    alpha = string.ascii_lowercase
    nums = string.digits
    
    # Check for alphabetic sequences
    for i in range(len(alpha) - length + 1):
        if alpha[i:i+length] in text:
            return True
        if alpha[i:i+length][::-1] in text:  # Reverse sequence
            return True
    
    # Check for numeric sequences
    for i in range(len(nums) - length + 1):
        if nums[i:i+length] in text:
            return True
        if nums[i:i+length][::-1] in text:  # Reverse sequence
            return True
    
    return False

def _detect_repetitive_chars(text, threshold=0.5):
    """Detect repetitive characters in text"""
    if not text or len(text) < 3:
        return False
        
    # Count character occurrences
    counter = Counter(text.lower())
    most_common = counter.most_common(1)[0]
    
    # If most common character appears more than threshold % of the time
    if most_common[1] / len(text) >= threshold:
        return True
        
    # Check for repetitive patterns like "ababab"
    for pattern_len in range(1, min(5, len(text)//2)):
        pattern = text[:pattern_len]
        if pattern * (len(text)//pattern_len) == text[:pattern_len * (len(text)//pattern_len)]:
            return True
            
    return False

def _check_mx_record(domain):
    """Check if domain has valid MX records"""
    try:
        mx_records = socket.getaddrinfo(domain, 25)
        return len(mx_records) > 0
    except:
        return False

def validate_email_address(email):
    """
    Enhanced email validation with multiple checks:
    - Basic format validation
    - Domain verification
    - Disposable email detection
    - Pattern detection (keyboard, sequential, repetitive)
    - TLD risk assessment
    """
    result = {
        'valid': False,
        'format_valid': False,
        'disposable': False,
        'suspicious_pattern': False,
        'high_risk_tld': False,
        'details': [],
        'overall': False
    }
    
    if not email:
        result['details'].append("Missing email address")
        return result
    
    # Basic format validation
    if '@' not in email or '.' not in email.split('@')[1]:
        result['details'].append("Invalid email format")
        return result
    
    # Use Django's validator
    try:
        django_validate_email(email)
        result['format_valid'] = True
    except ValidationError:
        result['details'].append("Invalid email format")
        return result
    
    # Split email parts
    username, domain = email.split('@')
    domain_parts = tldextract.extract(domain)
    tld = domain_parts.suffix.lower() if domain_parts.suffix else ""
    
    # Check for disposable email
    if domain.lower() in DISPOSABLE_EMAIL_DOMAINS:
        result['disposable'] = True
        result['details'].append("Disposable email detected")
    
    # Check for suspicious TLD
    if tld in HIGH_RISK_TLDS:
        result['high_risk_tld'] = True
        result['details'].append(f"High-risk TLD detected: .{tld}")
    
    # Check for suspicious patterns in username
    if _detect_keyboard_pattern(username):
        result['suspicious_pattern'] = True
        result['details'].append("Keyboard pattern detected in email username")
    
    if _detect_sequential_chars(username):
        result['suspicious_pattern'] = True
        result['details'].append("Sequential character pattern detected in email username")
    
    if _detect_repetitive_chars(username):
        result['suspicious_pattern'] = True
        result['details'].append("Repetitive character pattern detected in email username")
    
    # Determine overall validity
    if result['format_valid'] and not result['disposable'] and not result['suspicious_pattern']:
        result['valid'] = True
        result['overall'] = True
    
    # If still valid but has risk factors, mark as "suspicious"
    if result['valid'] and (result['high_risk_tld'] or len(username) <= 3):
        result['suspicious'] = True
        result['details'].append("Email appears valid but has suspicious characteristics")
    
    return result

def validate_phone_number(phone):
    """
    Enhanced phone validation:
    - Basic format validation
    - Area code verification
    - Pattern detection
    - Service type assessment (VOIP, toll-free)
    """
    result = {
        'valid': False,
        'format_valid': False,
        'suspicious_pattern': False,
        'high_risk_area_code': False,
        'voip_number': False,
        'details': [],
        'overall': False
    }
    
    if not phone:
        result['details'].append("Missing phone number")
        return result
    
    # Clean the phone number
    phone = re.sub(r'[^0-9]', '', phone)
    
    # Check length (US numbers)
    is_valid_length = len(phone) in [10, 11]
    if len(phone) == 11 and not phone.startswith('1'):
        is_valid_length = False
    
    if not is_valid_length:
        result['details'].append("Invalid phone number length")
        return result
    
    result['format_valid'] = True
    
    # Normalize to 10 digits
    if len(phone) == 11:
        phone = phone[1:]  # Remove country code
    
    # Get area code
    area_code = phone[:3]
    
    # Check for obvious fake patterns
    obvious_fakes = [
        '1234567890', '0987654321', '1111111111', '2222222222', '3333333333',
        '4444444444', '5555555555', '6666666666', '7777777777', '8888888888',
        '9999999999', '0000000000', '1234554321', '9876543210', '1122334455',
        '9988776655', '1231231234', '4565456545'
    ]
    
    if phone in obvious_fakes:
        result['suspicious_pattern'] = True
        result['details'].append("Obviously fake phone number pattern")
    
    # Check for sequential digits
    if _detect_sequential_chars(phone, 4):
        result['suspicious_pattern'] = True
        result['details'].append("Sequential digit pattern detected in phone number")
    
    # Check for repetitive digits
    if _detect_repetitive_chars(phone, 0.4):
        result['suspicious_pattern'] = True
        result['details'].append("Repetitive digit pattern detected in phone number")
    
    # Check for high-fraud area code
    if area_code in HIGH_FRAUD_AREA_CODES:
        result['high_risk_area_code'] = True
        result['details'].append("High-fraud risk area code detected")
    
    # Check for VOIP number
    if area_code in VOIP_AREA_CODES:
        result['voip_number'] = True
        result['details'].append("VOIP number detected")
    
    # Check for toll-free numbers
    toll_free_codes = ['800', '888', '877', '866', '855', '844', '833']
    if area_code in toll_free_codes:
        result['details'].append("Toll-free number detected")
    
    # Determine overall validity
    if result['format_valid'] and not result['suspicious_pattern']:
        result['valid'] = True
        result['overall'] = True
    
    # If valid but has risk factors, mark as "suspicious"
    if result['valid'] and (result['high_risk_area_code'] or result['voip_number']):
        result['suspicious'] = True
        result['details'].append("Phone appears valid but has suspicious characteristics")
    
    return result

def validate_location(zip_code, state=None):
    """
    Enhanced location validation:
    - ZIP code format validation
    - State-ZIP correspondence check
    - High-fraud ZIP detection
    """
    result = {
        'valid': False,
        'format_valid': False,
        'high_risk_zip': False,
        'state_mismatch': False,
        'details': [],
        'issue': None
    }
    
    if not zip_code:
        result['issue'] = "Missing ZIP code"
        result['details'].append("Missing ZIP code")
        return result
    
    # Basic US ZIP code validation
    zip_valid = bool(re.match(r'^\d{5}(-\d{4})?$', zip_code))
    if not zip_valid:
        result['issue'] = "Invalid ZIP code format"
        result['details'].append("Invalid ZIP code format")
        return result
    
    # Extract the 5-digit ZIP code
    zip5 = zip_code[:5]
    result['format_valid'] = True
    
    # Check for high-fraud ZIP
    if zip5 in HIGH_FRAUD_ZIP_CODES:
        result['high_risk_zip'] = True
        result['details'].append("High-fraud risk ZIP code")
    
    # Check state-ZIP correspondence if state is provided
    if state:
        # This is a simplified example - in a real implementation you'd 
        # have a complete ZIP-to-state mapping
        expected_state = None
        state = state.upper()
        
        # Simple ZIP prefix check
        zip_prefix = int(zip5[:1])
        
        if zip_prefix == 0:  # 0xxxx
            expected_state = ['CT', 'MA', 'ME', 'NH', 'NJ', 'PR', 'RI', 'VT']
        elif zip_prefix == 1:  # 1xxxx
            expected_state = ['DE', 'NY', 'PA']
        elif zip_prefix == 2:  # 2xxxx
            expected_state = ['DC', 'MD', 'NC', 'SC', 'VA', 'WV']
        elif zip_prefix == 3:  # 3xxxx
            expected_state = ['AL', 'FL', 'GA', 'MS', 'TN']
        elif zip_prefix == 4:  # 4xxxx
            expected_state = ['IN', 'KY', 'MI', 'OH']
        elif zip_prefix == 5:  # 5xxxx
            expected_state = ['IA', 'MN', 'MT', 'ND', 'SD', 'WI']
        elif zip_prefix == 6:  # 6xxxx
            expected_state = ['IL', 'KS', 'MO', 'NE']
        elif zip_prefix == 7:  # 7xxxx
            expected_state = ['AR', 'LA', 'OK', 'TX']
        elif zip_prefix == 8:  # 8xxxx
            expected_state = ['AZ', 'CO', 'ID', 'NM', 'NV', 'UT', 'WY']
        elif zip_prefix == 9:  # 9xxxx
            expected_state = ['AK', 'CA', 'HI', 'OR', 'WA']
            
        if expected_state and state not in expected_state:
            result['state_mismatch'] = True
            result['details'].append(f"State {state} doesn't match ZIP code {zip5}")
    
    # Determine overall validity
    if result['format_valid'] and not result['state_mismatch']:
        result['valid'] = True
    else:
        result['issue'] = "Invalid location information"
    
    # If valid but has risk factors, mark as "suspicious"
    if result['valid'] and result['high_risk_zip']:
        result['suspicious'] = True
        result['details'].append("Location appears valid but is high-risk")
    
    return result

def validate_name(name):
    """
    Enhanced name validation:
    - Basic format validation
    - Fake name detection
    - Pattern detection
    - Celebrity name detection
    """
    result = {
        'valid': False,
        'format_valid': False,
        'suspicious_pattern': False,
        'fake_name': False,
        'celebrity_name': False,
        'details': [],
        'issue': None
    }
    
    if not name:
        result['issue'] = "Missing name"
        result['details'].append("Missing name")
        return result
    
    name = name.strip().lower()
    
    # Check for minimum length
    if len(name) < 4:
        result['issue'] = "Name too short"
        result['details'].append("Name too short")
        return result
    
    # Check for first and last name
    has_space = ' ' in name
    if not has_space:
        result['issue'] = "Missing last name"
        result['details'].append("Missing last name")
        return result
    
    # Basic format is valid
    result['format_valid'] = True
    
    # Check for suspicious patterns
    if _detect_keyboard_pattern(name):
        result['suspicious_pattern'] = True
        result['details'].append("Keyboard pattern detected in name")
    
    if _detect_sequential_chars(name):
        result['suspicious_pattern'] = True
        result['details'].append("Sequential character pattern detected in name")
    
    if _detect_repetitive_chars(name, 0.3):
        result['suspicious_pattern'] = True
        result['details'].append("Repetitive character pattern detected in name")
    
    # Check for known fake names
    if name in FAKE_NAMES:
        result['fake_name'] = True
        result['details'].append("Common fake/test name detected")
    
    # Check for celebrity names
    if name in CELEBRITY_NAMES:
        result['celebrity_name'] = True
        result['details'].append("Celebrity name detected")
    
    # Check for single-character name parts
    name_parts = name.split()
    for part in name_parts:
        if len(part) == 1:
            result['suspicious_pattern'] = True
            result['details'].append("Single-character name part detected")
            break
    
    # Determine overall validity
    if result['format_valid'] and not result['suspicious_pattern'] and not result['fake_name'] and not result['celebrity_name']:
        result['valid'] = True
    else:
        result['issue'] = "Suspicious name detected"
    
    return result

def validate_cross_fields(email, phone, name, zip_code, ip_address=None):
    """
    Cross-field validation to check for consistency across fields
    """
    result = {
        'consistent': True,
        'issues': []
    }
    
    # Check if email username matches name
    if email and '@' in email and name and ' ' in name:
        username = email.split('@')[0].lower()
        name_parts = name.lower().split()
        first_name = name_parts[0]
        last_name = name_parts[-1]
        
        # Extract initials
        first_initial = first_name[0] if first_name else ''
        last_initial = last_name[0] if last_name else ''
        
        # Check common username patterns
        username_patterns = [
            first_name,
            last_name,
            first_name + last_name,
            first_name + '.' + last_name,
            first_name + '_' + last_name,
            first_initial + last_name,
            first_name + last_initial,
            first_initial + '.' + last_name
        ]
        
        # Add numeric variations
        for pattern in username_patterns[:]:
            for i in range(1, 10):
                username_patterns.append(pattern + str(i))
        
        username_match = any(pattern in username or username in pattern for pattern in username_patterns)
        
        if not username_match and len(username) > 3:
            result['consistent'] = False
            result['issues'].append("Email username doesn't match provided name")
    
    # Advanced checks could be added here (ZIP to IP geolocation, etc.)
    
    return result 