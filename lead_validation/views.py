from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
import logging
from lead_capture.models import Lead
from .utils import validate_and_store_lead_data

logger = logging.getLogger(__name__)

@api_view(['POST'])
def validate_lead_api(request):
    """REST API endpoint for lead validation - now uses the centralized utils function"""
    data = request.data
    logger.info("Received lead validation request")
    
    # Create a temporary lead object to leverage the same validation logic
    temp_lead = Lead(
        name=data.get('name', ''),
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        zip_code=data.get('zip_code', ''),
        state=data.get('state', ''),
        address=data.get('address', ''),
        ip_address=data.get('ip_address', request.META.get('REMOTE_ADDR')),
        user_agent=data.get('user_agent', request.META.get('HTTP_USER_AGENT')),
        # Don't actually save this to DB
    )
    
    # Use the same validation function for consistency
    validation_result = validate_and_store_lead_data(temp_lead, save_to_db=False)
    
    # Format the response to match the API expected format
    results = {
        'score': validation_result['score'],
        'max_score': 100,
        'issues': [],
        'validations': validation_result['validation_results'],
    }
    
    # Extract issues from validation results
    validations = validation_result['validation_results']
    
    # Get issues from AI assessment if available
    if 'ai_assessment' in validations and 'issues' in validations['ai_assessment']:
        results['issues'] = validations['ai_assessment'].get('issues', [])
    
    # Add issues from rule-based validation
    for field in ['email', 'phone', 'location', 'name']:
        if field in validations and not validations[field].get('valid', False):
            issue = validations[field].get('issue', f'Invalid {field}')
            if issue not in results['issues']:
                results['issues'].append(issue)
    
    # Final assessment
    if results['score'] < 20:
        results['assessment'] = "High Risk"
        results['recommendation'] = "Reject"
    elif results['score'] < 70:
        results['assessment'] = "Medium Risk"
        results['recommendation'] = "Review"
    else:
        results['assessment'] = "Low Risk"
        results['recommendation'] = "Approve"
    
    return Response(results)

@login_required
def validate_existing_lead(request, lead_id):
    """View to validate an existing lead in the database"""
    lead = get_object_or_404(Lead, id=lead_id)
    
    # Check if the current user owns the lead
    if lead.agent != request.user and not request.user.is_staff:
        return JsonResponse({'error': 'You do not have permission to validate this lead'}, status=403)
    
    # Use the same validation function used by automated processes
    result = validate_and_store_lead_data(lead)
    
    return JsonResponse({
        'success': True,
        'lead_id': lead.id,
        'score': result['score'],
        'validation_results': result['validation_results']
    })