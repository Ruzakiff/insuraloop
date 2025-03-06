from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.conf import settings
from .models import Lead

@receiver(post_save, sender=Lead)
def notify_agent_of_new_lead(sender, instance, created, **kwargs):
    """Send an email notification to the agent when a new lead is created"""
    if created:
        lead = instance
        agent = lead.agent
        
        # Generate the dashboard URL
        dashboard_url = f"{settings.BASE_URL}{reverse('referral_system:my_links')}"
        
        # Create the context for the email template with default values for empty fields
        context = {
            'agent_name': agent.get_full_name() or agent.username,
            'lead_name': lead.name or "Not provided",
            'lead_email': lead.email or "Not provided", 
            'lead_phone': lead.phone or "Not provided",
            'insurance_type': lead.get_insurance_type_display() if hasattr(lead, 'get_insurance_type_display') else lead.insurance_type or "Not specified",
            'dashboard_url': dashboard_url,
            'date_submitted': lead.created_at.strftime("%B %d, %Y at %I:%M %p") if lead.created_at else "Just now",
            'referral_source': lead.referral_link.name if lead.referral_link else "Direct Referral",
        }
        
        # Render the email content from a template
        email_subject = f"New Lead: {lead.name or 'New Lead'} - {lead.get_insurance_type_display() if hasattr(lead, 'get_insurance_type_display') else lead.insurance_type or 'Insurance Lead'}"
        email_html = render_to_string('lead_capture/email/new_lead_notification.html', context)
        email_plain = render_to_string('lead_capture/email/new_lead_notification.txt', context)
        
        # Send the email
        send_mail(
            subject=email_subject,
            message=email_plain,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[agent.email],
            html_message=email_html,
            fail_silently=False,
        ) 