# accounts/views.py - Updated with proper redirects

from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.views import LogoutView
from django.urls import reverse_lazy
from .forms import RegisterForm


def register_view(request):
    """Register new user and redirect to food ordering page"""
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            # Redirect to food ordering page after registration
            return redirect("food_ordering")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


class CustomLogoutView(LogoutView):
    """Logout and redirect to landing page"""
    next_page = reverse_lazy('landing_page')