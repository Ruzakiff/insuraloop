from django import forms
from .models import Lead

class LeadCaptureForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['name', 'email', 'phone', 'insurance_type', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your.email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(123) 456-7890'}),
            'insurance_type': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Tell us about your insurance needs...'}),
        } 