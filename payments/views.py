# payments/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.contrib import messages
from .models import MpesaPayment
from foods.models import Cart, CartItem
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
        
        # Get ACTIVE cart and calculate total
        try:
            cart = Cart.objects.get(user=request.user, is_active=True)
            cart_items = CartItem.objects.filter(cart=cart)
            amount = int(cart.total_price())  # M-Pesa amount must be integer
            
            if amount <= 0:
                messages.error(request, 'Your cart is empty')
                return redirect('view_cart')
            
        except Cart.DoesNotExist:
            messages.error(request, 'Cart not found')
            return redirect('view_cart')
        
        # Format phone number (remove leading 0, add 254)
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif not phone_number.startswith('254'):
            phone_number = '254' + phone_number
        
        # Get access token
        access_token = get_mpesa_access_token()
        if not access_token:
            messages.error(request, 'Failed to authenticate with M-Pesa')
            return redirect('view_cart')
        
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
                # Save payment record with cart reference
                payment = MpesaPayment.objects.create(
                    user=request.user,
                    phone_number=phone_number,
                    amount=amount,
                    merchant_request_id=response_data.get('MerchantRequestID'),
                    checkout_request_id=response_data.get('CheckoutRequestID'),
                    status='pending'
                )
                
                # Store cart ID in session for later reference
                request.session['pending_cart_id'] = cart.id
                request.session['pending_payment_id'] = payment.id
                
                # Redirect to confirmation page with pending status
                return redirect('payment_confirmation', payment_id=payment.id)
            else:
                messages.error(request, response_data.get('errorMessage', 'Payment request failed'))
                return redirect('view_cart')
                
        except Exception as e:
            print(f"STK Push Error: {str(e)}")
            messages.error(request, 'Failed to initiate payment. Please try again.')
            return redirect('view_cart')
    
    # GET request - redirect to cart
    return redirect('view_cart')


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
                    
                    # Mark user's ACTIVE cart as completed (inactive)
                    try:
                        cart = Cart.objects.get(user=payment.user, is_active=True)
                        cart.is_active = False
                        cart.save()
                        print(f"Cart {cart.id} marked as inactive after successful payment")
                    except Cart.DoesNotExist:
                        print(f"No active cart found for user {payment.user.id}")
                    
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
def payment_confirmation(request, payment_id):
    """Show payment confirmation/receipt page"""
    payment = get_object_or_404(MpesaPayment, id=payment_id, user=request.user)
    
    # Get cart items (use the cart from session if available)
    cart_id = request.session.get('pending_cart_id')
    cart_items = []
    
    if cart_id:
        try:
            cart = Cart.objects.get(id=cart_id)
            cart_items = CartItem.objects.filter(cart=cart)
        except Cart.DoesNotExist:
            pass
    else:
        # Fallback: try to get active cart
        try:
            cart = Cart.objects.get(user=request.user, is_active=True)
            cart_items = CartItem.objects.filter(cart=cart)
        except Cart.DoesNotExist:
            pass
    
    # Calculate total with item totals
    for item in cart_items:
        item.total_price = item.food.price * item.quantity
    
    # Determine payment status
    if payment.status == 'completed':
        payment_status = 'success'
    elif payment.status == 'pending':
        payment_status = 'pending'
    else:
        payment_status = 'failed'
    
    context = {
        'payment_status': payment_status,
        'transaction_id': payment.mpesa_receipt_number or payment.checkout_request_id,
        'phone_number': payment.phone_number,
        'amount': payment.amount,
        'payment_date': payment.transaction_date or payment.created_at,
        'cart_items': cart_items,
        'error_message': payment.result_desc if payment.status == 'failed' else None,
    }
    
    return render(request, 'payments/confirmation.html', context)


@login_required
def check_payment_status(request, payment_id):
    """AJAX endpoint to check payment status and redirect if completed"""
    try:
        payment = MpesaPayment.objects.get(id=payment_id, user=request.user)
        
        # If payment completed, mark cart as inactive
        if payment.status == 'completed':
            try:
                cart = Cart.objects.get(user=request.user, is_active=True)
                if cart:
                    cart.is_active = False
                    cart.save()
            except Cart.DoesNotExist:
                pass
        
        return JsonResponse({
            'status': payment.status,
            'result_desc': payment.result_desc,
            'mpesa_receipt': payment.mpesa_receipt_number,
            'should_refresh': payment.status in ['completed', 'failed']
        })
    except MpesaPayment.DoesNotExist:
        return JsonResponse({'error': 'Payment not found'}, status=404)


# Optional: Keep old payment_status view for backwards compatibility
@login_required
def payment_status(request, payment_id):
    """Redirect to new confirmation page"""
    return redirect('payment_confirmation', payment_id=payment_id)