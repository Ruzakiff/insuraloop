from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from .forms import UserRegistrationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django import forms
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.http import HttpResponse

# Create your views here.

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}!')
            
            # Log the user in
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            
            return redirect('referral_system:my_referral_links')
    else:
        form = UserRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('login')

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

@login_required
def profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, 'accounts/profile.html', {'form': form})

@ensure_csrf_cookie  # Ensure the CSRF cookie is set
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            # Redirect to a success page.
            return redirect('referral_system:my_links')
        else:
            # Return an 'invalid login' error message.
            return render(request, 'accounts/login.html', {'form_errors': True})
    
    return render(request, 'accounts/login.html')

@ensure_csrf_cookie
def debug_csrf(request):
    token = request.META.get('CSRF_COOKIE', None)
    cookie = request.COOKIES.get('csrftoken', None)
    
    return HttpResponse(
        f"CSRF Debug:<br>"
        f"Cookie set: {'Yes' if cookie else 'No'}<br>"
        f"Token in META: {'Yes' if token else 'No'}<br>"
        f"Headers: {request.headers.get('Cookie', 'None')}"
    )

def test_form(request):
    """A simple test form to isolate CSRF issues"""
    context = {}
    
    if request.method == 'POST':
        context['success'] = True
    
    return render(request, 'accounts/test_form.html', context)
