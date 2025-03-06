from django.core.management.base import BaseCommand
from referral_system.models import PaymentRate

class Command(BaseCommand):
    help = 'Sets up default payment rates for referrals'

    def handle(self, *args, **options):
        # Clear any existing rates if specified
        if options.get('clear', False):
            PaymentRate.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleared all existing payment rates'))
        
        # Set up nationwide default rates
        defaults = [
            ('', 'auto', 25.00),  # Nationwide auto
            ('', 'home', 30.00),  # Nationwide home
            ('', 'life', 20.00),  # Nationwide life
            ('', 'health', 22.00),  # Nationwide health
            ('', 'business', 35.00),  # Nationwide business
            ('', 'other', 20.00),  # Nationwide other
        ]
        
        # State-specific rates - add any states that have different rates
        state_specific = [
            ('CA', 'auto', 35.00),  # California Auto
            ('CA', 'home', 40.00),  # California Home
            ('CA', 'business', 45.00),  # California Business
            ('NY', 'auto', 30.00),  # New York Auto
            ('NY', 'home', 35.00),  # New York Home
            ('TX', 'auto', 28.00),  # Texas Auto
            ('FL', 'auto', 30.00),  # Florida Auto
            ('FL', 'home', 32.00),  # Florida Home
        ]
        
        # Combine all rates
        all_rates = defaults + state_specific
        
        # Create the rates
        for state, insurance_type, amount in all_rates:
            PaymentRate.objects.update_or_create(
                state=state,
                insurance_type=insurance_type,
                defaults={'rate_amount': amount}
            )
            
            state_name = "Nationwide" if state == "" else state
            self.stdout.write(self.style.SUCCESS(
                f'Set {state_name} {insurance_type} rate to ${amount}'
            ))
        
        self.stdout.write(self.style.SUCCESS('Successfully set up payment rates'))
        
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing rates before setting up new ones',
        ) 