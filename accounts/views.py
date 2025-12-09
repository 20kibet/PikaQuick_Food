# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.views import LogoutView
from django.urls import reverse_lazy
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from .forms import RegisterForm


def register_view(request):
    """Register new user and send email + redirect"""
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)

            # Get form data
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')

            # Send Welcome Email
            subject = "Welcome to our Platform!"
            message = render_to_string('accounts/email.html', {'username': username})


            try:
                email_message = EmailMessage(
                    subject,
                    message,
                    settings.EMAIL_HOST_USER,
                    [email]
                )
                email_message.content_subtype = 'html'
                email_message.send()
                print("Email sent successfully!")
            except Exception as e:
                print(f"❌ Email error: {e}")

            return redirect("food_ordering")  # Where you want after registration
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


class CustomLogoutView(LogoutView):
    """Logout and redirect to landing page"""
    next_page = reverse_lazy('landing_page')
