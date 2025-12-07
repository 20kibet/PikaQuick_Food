from django.contrib import admin
from .models import MpesaPayment

@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'phone_number', 'amount', 'status', 'mpesa_receipt_number', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['phone_number', 'mpesa_receipt_number', 'user__username']
    readonly_fields = ['created_at', 'updated_at']