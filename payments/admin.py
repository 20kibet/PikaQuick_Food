from django.contrib import admin
from .models import MpesaPayment

@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'phone_number', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['phone_number', 'mpesa_receipt_number', 'user__username']
    readonly_fields = ['merchant_request_id', 'checkout_request_id', 'mpesa_receipt_number', 'created_at', 'updated_at']