from django.shortcuts import render, redirect
from .forms import CustomUserCreationForm
from .emails import send_welcome_email  # import the function

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Send welcome email
            send_welcome_email(user)
            
            return redirect('login')  # or wherever you want
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/register.html', {'form': form})
