from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.conf import settings
from .models import Lead

@receiver(post_save, sender=Lead)
def notify_agent_of_new_lead(sender, instance, created, **kwargs):
    """Send email notification when a new lead is created"""
    if created and instance.agent:
        # Get agent email
        agent_email = instance.agent.email
        
        # Build dashboard URL
        dashboard_url = f"{settings.BASE_URL}{reverse('referral_system:my_referral_links')}"
        
        # Prepare email context
        context = {
            'lead': instance,
            'agent': instance.agent,
            'dashboard_url': dashboard_url,
        }
        
        # Render email templates
        html_message = render_to_string('lead_capture/emails/new_lead_notification.html', context)
        plain_message = render_to_string('lead_capture/emails/new_lead_notification.txt', context)
        
        # Send email
        send_mail(
            subject=f'New Lead: {instance.name} - {instance.get_insurance_type_display()}',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[agent_email],
            html_message=html_message,
            fail_silently=False,
        ) 