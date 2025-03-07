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
    print(f"Lead data received: {lead_data}")
    
    if not openai.api_key:
        print("ERROR: OpenAI API key not configured!")
        logger.error("OpenAI API key not configured")
        return {"error": "AI validation unavailable", "score": 0, "details": []}
    
    try:
        print(f"Using OpenAI API key: {openai.api_key[:5]}...{openai.api_key[-4:] if len(openai.api_key) > 8 else ''}")
        
        # Prepare the prompt
        prompt = f"""
        Analyze this lead information for potential fraud or validity issues:
        
        Name: {lead_data.get('name', 'Not provided')}
        Email: {lead_data.get('email', 'Not provided')}
        Phone: {lead_data.get('phone', 'Not provided')}
        ZIP Code: {lead_data.get('zip_code', 'Not provided')}
        State: {lead_data.get('state', 'Not provided')}
        
        Provide a JSON response with:
        1. risk_score: number from 0-100 (higher = more risky)
        2. issues: list of specific issues detected
        3. assessment: "low_risk", "medium_risk", or "high_risk"
        4. confidence: number from 0-100 on confidence in assessment
        
        Be especially vigilant for:
        - Disposable emails
        - Keyboard pattern emails (qwerty, asdf, etc.)
        - Suspicious naming patterns
        - Fake phone numbers
        - Mismatched location info
        - Mismatches between fields (e.g., email name vs provided name)
        - Common fraud patterns
        
        Format the response as valid JSON only.
        """
        
        print("Calling OpenAI API...")
        
        # Call OpenAI API
        response = openai.chat.completions.create(
            model="gpt-4o",  # Use the best available model
            messages=[
                {"role": "system", "content": "You are a fraud detection expert that analyzes lead data for insurance companies. You only respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Low temperature for consistent results
            response_format={"type": "json_object"}
        )
        
        print("OpenAI API response received!")
        
        # Parse the response
        result = json.loads(response.choices[0].message.content)
        
        # Add timestamp and model info
        result['ai_model'] = "gpt-4o"
        
        print("AI VALIDATION RESULT:")
        print(json.dumps(result, indent=2))
        
        return result
    
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