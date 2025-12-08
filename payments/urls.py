# payments/urls.py
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
   
    path('initiate/', views.initiate_payment, name='initiate_payment'),
    path('callback/', views.mpesa_callback, name='mpesa_callback'),
    path('check-status/<int:payment_id>/', views.check_payment_status, name='check_status'),
    path('confirmation/<int:payment_id>/', views.payment_confirmation, name='payment_confirmation'),
    path('status/<int:payment_id>/', views.payment_status, name='payment_status'),
]