from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
import logging
from lead_capture.models import Lead
from .utils import validate_and_store_lead_data, check_for_duplicate_lead

logger = logging.getLogger(__name__)

@api_view(['POST'])
def validate_lead_api(request):
    """REST API endpoint for lead validation using our hybrid scoring system"""
    data = request.data
    logger.info(f"Received lead validation request: {data.get('email', 'no-email')}")
    
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
    
    try:
        # Use our enhanced hybrid validation function
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
        
        # Check if this is a duplicate - look for it in both locations
        is_duplicate = False
        if 'duplicate_check' in validations and validations['duplicate_check'].get('is_duplicate', False):
            dup_check = validations['duplicate_check']
            is_duplicate = True
            results['duplicate_detected'] = True
            results['duplicate_confidence'] = dup_check.get('confidence', 0)
            results['matching_lead_ids'] = dup_check.get('matching_lead_ids', [])
            results['issues'].append(f"Duplicate lead detected with {dup_check.get('confidence', 0)}% confidence")
        
        # Also check the score_breakdown for duplicate info (different versions of the code)
        if not is_duplicate and 'score_breakdown' in validations and validations['score_breakdown'].get('is_duplicate', False):
            results['duplicate_detected'] = True
            results['duplicate_confidence'] = validations['score_breakdown'].get('duplicate_confidence', 0)
            results['issues'].append(f"Duplicate lead detected with {validations['score_breakdown'].get('duplicate_confidence', 0)}% confidence")
        
        # Get issues from AI assessment if available
        if 'ai_assessment' in validations and 'issues' in validations['ai_assessment']:
            results['issues'].extend(validations['ai_assessment'].get('issues', []))
        
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
    
    except Exception as e:
        logger.error(f"Error validating lead: {str(e)}")
        return Response({
            'error': 'Validation failed',
            'message': str(e)
        }, status=500)

@login_required
def validate_existing_lead(request, lead_id):
    """View to validate an existing lead in the database using our hybrid scoring"""
    lead = get_object_or_404(Lead, id=lead_id)
    
    # Check if the current user owns the lead
    if lead.agent != request.user and not request.user.is_staff:
        return JsonResponse({'error': 'You do not have permission to validate this lead'}, status=403)
    
    try:
        # Use our enhanced hybrid validation function - exactly the same as API endpoint
        result = validate_and_store_lead_data(lead)
        
        # Format the response to match the API expected format for consistency
        response_data = {
            'success': True,
            'lead_id': lead.id,
            'score': result['score'],
            'max_score': 100,
            'validations': result['validation_results'],
            'issues': []
        }
        
        # Extract issues from validation results (same as in API endpoint)
        validations = result['validation_results']
        
        # Get issues from AI assessment if available
        if 'ai_assessment' in validations and 'issues' in validations['ai_assessment']:
            response_data['issues'].extend(validations['ai_assessment'].get('issues', []))
        
        # Add issues from rule-based validation
        for field in ['email', 'phone', 'location', 'name']:
            if field in validations and not validations[field].get('valid', False):
                issue = validations[field].get('issue', f'Invalid {field}')
                if issue not in response_data['issues']:
                    response_data['issues'].append(issue)
        
        # Final assessment (same as API endpoint)
        if result['score'] < 20:
            response_data['assessment'] = "High Risk"
            response_data['recommendation'] = "Reject"
        elif result['score'] < 70:
            response_data['assessment'] = "Medium Risk"
            response_data['recommendation'] = "Review"
        else:
            response_data['assessment'] = "Low Risk"
            response_data['recommendation'] = "Approve"
        
        return JsonResponse(response_data)
    
    except Exception as e:
        logger.error(f"Error validating lead {lead_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)