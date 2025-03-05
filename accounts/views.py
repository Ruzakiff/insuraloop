from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages

# Create your views here.

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
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
        form = UserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('login')
