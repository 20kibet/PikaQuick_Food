from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.views import LogoutView
from django.urls import reverse_lazy
from .forms import RegisterForm

def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")  # Goes to foods/home.html
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})

class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('home')