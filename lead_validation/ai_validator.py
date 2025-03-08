import openai
import os
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Configure OpenAI API
openai.api_key = getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))

def analyze_lead_with_ai(lead_data):
    """
    Use OpenAI API to analyze lead data for potential fraud
    Returns a dict with risk assessment
    """
    print("AI VALIDATOR STARTING - analyzing lead data...")
    insurance_type = lead_data.get('insurance_type', '')
    print(f"Processing insurance type: {insurance_type}")
    print(f"Lead data keys: {list(lead_data.keys())}")
    
    if not openai.api_key:
        print("ERROR: OpenAI API key not configured!")
        logger.error("OpenAI API key not configured")
        return {"error": "AI validation unavailable", "score": 0, "details": []}
    
    try:
        print(f"Using OpenAI API key: {openai.api_key[:5]}...{openai.api_key[-4:] if len(openai.api_key) > 8 else ''}")
        
        # Prepare the prompt with additional fields based on insurance type
        
        base_prompt = f"""
        Analyze this lead information for potential fraud or validity issues:
        
        Name: {lead_data.get('name', 'Not provided')}
        Email: {lead_data.get('email', 'Not provided')}
        Phone: {lead_data.get('phone', 'Not provided')}
        ZIP Code: {lead_data.get('zip_code', 'Not provided')}
        Address: {lead_data.get('address', 'Not provided')}
        IP Address: {lead_data.get('ip_address', 'Not provided')}
        Insurance Type: {insurance_type}
        Notes: {lead_data.get('notes', 'Not provided')}
        """
        
        # Add insurance-specific fields to the prompt
        if insurance_type == 'auto':
            auto_details = f"""
            Auto Insurance Details:
            Vehicle VIN: {lead_data.get('vehicle_vin', 'Not provided')}
            Vehicle Year: {lead_data.get('vehicle_year', 'Not provided')}
            Vehicle Make: {lead_data.get('vehicle_make', 'Not provided')}
            Vehicle Model: {lead_data.get('vehicle_model', 'Not provided')}
            Vehicle Usage: {lead_data.get('vehicle_usage', 'Not provided')}
            Annual Mileage: {lead_data.get('annual_mileage', 'Not provided')}
            Date of Birth: {lead_data.get('date_of_birth', 'Not provided')}
            Current Insurer: {lead_data.get('current_insurer', 'Not provided')}
            """
            base_prompt += auto_details
            
        elif insurance_type == 'home':
            home_details = f"""
            Home Insurance Details:
            Property Type: {lead_data.get('property_type', 'Not provided')}
            Ownership Status: {lead_data.get('ownership_status', 'Not provided')}
            Year Built: {lead_data.get('year_built', 'Not provided')}
            Square Footage: {lead_data.get('square_footage', 'Not provided')}
            Bedrooms: {lead_data.get('num_bedrooms', 'Not provided')}
            Bathrooms: {lead_data.get('num_bathrooms', 'Not provided')}
            Current Insurer: {lead_data.get('current_insurer', 'Not provided')}
            """
            base_prompt += home_details
            
        elif insurance_type == 'business':
            business_details = f"""
            Business Insurance Details:
            Business Name: {lead_data.get('business_name', 'Not provided')}
            Business Address: {lead_data.get('business_address', 'Not provided')}
            Industry: {lead_data.get('industry', 'Not provided')}
            Number of Employees: {lead_data.get('num_employees', 'Not provided')}
            Annual Revenue: {lead_data.get('annual_revenue', 'Not provided')}
            Current Insurer: {lead_data.get('current_insurer', 'Not provided')}
            """
            base_prompt += business_details
        
        # Add the standard JSON request format
        prompt = base_prompt + """
        
        Analyze the lead data and provide a comprehensive assessment in the following JSON format:
        
        {
          "duplicate_check": {
            "is_duplicate": boolean,
            "confidence": number from 0-100,
            "matching_lead_ids": [],
            "matching_fields": []
          },
          
          "ai_assessment": {
            "risk_score": number from 0-100 (higher = more risky),
            "assessment": "low_risk", "medium_risk", or "high_risk",
            "confidence": number from 0-100,
            "issues": [list of specific issues detected],
            "ai_model": "gpt-4o"
          },
          
          "email": {
            "valid": boolean,
            "issue": string or null,
            "domain_risk": "low", "medium", or "high"
          },
          
          "phone": {
            "valid": boolean,
            "country_code": string or null,
            "formatted": string or null
          },
          
          "name": {
            "valid": boolean,
            "name_parts": {
              "first_name": string,
              "last_name": string
            }
          },
          
          "location": {
            "valid": boolean,
            "derived_state": string or null,
            "matches_ip_location": boolean
          },
          
          "cross_field": {
            "consistent": boolean,
            "issues": [list of inconsistencies between fields]
          }
        }
        
        Be especially vigilant for:
        - Disposable emails
        - Keyboard pattern emails (qwerty, asdf, etc.)
        - Suspicious naming patterns
        - Fake phone numbers
        - Mismatched location info
        - Mismatches between fields (e.g., email name vs provided name)
        - Common fraud patterns
        - Inconsistencies in the provided insurance details
        
        Format the response as valid JSON only.
        """
        
        print("Calling OpenAI API...")
        
        # Call OpenAI API
        response = openai.chat.completions.create(
            model="gpt-4o",  # Use the best available model
            messages=[
                {"role": "system", "content": "You are a fraud detection expert that analyzes lead data for insurance companies. You only respond with valid JSON that exactly matches the requested format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,  # Low temperature for consistent results
            response_format={"type": "json_object"}
        )
        
        print("OpenAI API response received!")
        
        # Parse the response
        result = json.loads(response.choices[0].message.content)
        
        # Add timestamp and model info
        result['ai_model'] = "gpt-4o"
        
        # Add field to indicate this is the AI result, not DB duplicate check
        if "duplicate_check" in result:
            # Rename the field to avoid confusion with our database check
            result["ai_duplicate_assessment"] = result.pop("duplicate_check")
            print("Renamed AI duplicate_check to ai_duplicate_assessment")
        
        print("AI VALIDATION RESULT:")
        print(json.dumps(result, indent=2))
        
        # Ensure result is a valid dictionary before returning
        if isinstance(result, dict):
            return result
        else:
            logger.error(f"AI returned non-dictionary result: {result}")
            return {
                "error": "AI validation returned invalid format",
                "risk_score": 50,
                "issues": ["AI validation format error"],
                "assessment": "medium_risk",
                "confidence": 0
            }
    
    except Exception as e:
        print(f"ERROR IN AI VALIDATION: {str(e)}")
        logger.error(f"Error using OpenAI API: {str(e)}")
        # Return fallback assessment
        return {
            "error": f"AI validation failed: {str(e)}",
            "risk_score": 50,  # Neutral score when AI fails
            "issues": ["AI validation unavailable - using fallback rules"],
            "assessment": "medium_risk",
            "confidence": 0
        } 