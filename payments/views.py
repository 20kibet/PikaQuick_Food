# payments/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from .models import MpesaPayment
from foods.models import Cart
import requests
import base64
from datetime import datetime
import json


def get_mpesa_access_token():
    """Get OAuth access token from Daraja API"""
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    api_url = f"{settings.MPESA_SANDBOX_BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
    
    try:
        response = requests.get(api_url, auth=(consumer_key, consumer_secret))
        response.raise_for_status()
        return response.json()['access_token']
    except Exception as e:
        print(f"Error getting access token: {str(e)}")
        return None


@login_required
def initiate_payment(request):
    """Initiate M-Pesa STK Push payment"""
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        
        # Get cart and calculate total
        try:
            cart = Cart.objects.get(user=request.user)
            amount = int(cart.total_price())  # M-Pesa amount must be integer
            
            if amount <= 0:
                return JsonResponse({'error': 'Cart is empty'}, status=400)
            
        except Cart.DoesNotExist:
            return JsonResponse({'error': 'Cart not found'}, status=404)
        
        # Format phone number (remove leading 0, add 254)
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif not phone_number.startswith('254'):
            phone_number = '254' + phone_number
        
        # Get access token
        access_token = get_mpesa_access_token()
        if not access_token:
            return JsonResponse({'error': 'Failed to authenticate with M-Pesa'}, status=500)
        
        # Prepare STK Push request
        api_url = f"{settings.MPESA_SANDBOX_BASE_URL}/mpesa/stkpush/v1/processrequest"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(
            f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()
        ).decode('utf-8')
        
        payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": settings.MPESA_SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": settings.MPESA_CALLBACK_URL,
            "AccountReference": f"PikaQuick-{request.user.id}",
            "TransactionDesc": "Food Order Payment"
        }
        
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            response_data = response.json()
            
            if response_data.get('ResponseCode') == '0':
                # Save payment record
                payment = MpesaPayment.objects.create(
                    user=request.user,
                    phone_number=phone_number,
                    amount=amount,
                    merchant_request_id=response_data.get('MerchantRequestID'),
                    checkout_request_id=response_data.get('CheckoutRequestID'),
                    status='pending'
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Payment request sent. Please check your phone.',
                    'checkout_request_id': response_data.get('CheckoutRequestID'),
                    'payment_id': payment.id
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': response_data.get('errorMessage', 'Payment request failed')
                }, status=400)
                
        except Exception as e:
            print(f"STK Push Error: {str(e)}")
            return JsonResponse({'error': 'Failed to initiate payment'}, status=500)
    
    # GET request - show payment form
    try:
        cart = Cart.objects.get(user=request.user)
        total = cart.total_price()
    except Cart.DoesNotExist:
        total = 0
    
    return render(request, 'payments/initiate_payment.html', {'total': total})


@csrf_exempt
def mpesa_callback(request):
    """Handle M-Pesa callback after payment"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Extract callback data
            stk_callback = data.get('Body', {}).get('stkCallback', {})
            merchant_request_id = stk_callback.get('MerchantRequestID')
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc')
            
            # Find payment record
            try:
                payment = MpesaPayment.objects.get(
                    checkout_request_id=checkout_request_id
                )
                
                payment.result_code = str(result_code)
                payment.result_desc = result_desc
                
                if result_code == 0:
                    # Payment successful
                    callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                    
                    for item in callback_metadata:
                        if item.get('Name') == 'MpesaReceiptNumber':
                            payment.mpesa_receipt_number = item.get('Value')
                        elif item.get('Name') == 'TransactionDate':
                            transaction_date = str(item.get('Value'))
                            payment.transaction_date = datetime.strptime(
                                transaction_date, '%Y%m%d%H%M%S'
                            )
                    
                    payment.status = 'completed'
                    
                    # Clear user's cart
                    try:
                        cart = Cart.objects.get(user=payment.user)
                        cart.items.all().delete()
                    except Cart.DoesNotExist:
                        pass
                    
                else:
                    # Payment failed
                    payment.status = 'failed'
                
                payment.save()
                
            except MpesaPayment.DoesNotExist:
                print(f"Payment not found for checkout request: {checkout_request_id}")
            
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
            
        except Exception as e:
            print(f"Callback Error: {str(e)}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Failed'})
    
    return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid request'})


@login_required
def payment_status(request, payment_id):
    """Check payment status"""
    payment = get_object_or_404(MpesaPayment, id=payment_id, user=request.user)
    
    return render(request, 'payments/payment_status.html', {'payment': payment})


@login_required
def check_payment_status(request, payment_id):
    """AJAX endpoint to check payment status"""
    try:
        payment = MpesaPayment.objects.get(id=payment_id, user=request.user)
        return JsonResponse({
            'status': payment.status,
            'result_desc': payment.result_desc,
            'mpesa_receipt': payment.mpesa_receipt_number
        })
    except MpesaPayment.DoesNotExist:
        return JsonResponse({'error': 'Payment not found'}, status=404)