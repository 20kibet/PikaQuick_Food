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
import logging

logger = logging.getLogger(__name__)


def get_mpesa_access_token():
    """Get OAuth access token from Daraja API"""
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    # Ensure MPESA_SANDBOX_BASE_URL is set in settings.py (e.g., https://sandbox.safaricom.co.ke)
    api_url = f"{settings.MPESA_SANDBOX_BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
    
    try:
        response = requests.get(api_url, auth=(consumer_key, consumer_secret))
        response.raise_for_status()
        return response.json()['access_token']
    except Exception as e:
        logger.error(f"Error getting access token: {str(e)}")
        return None


@login_required
def initiate_payment(request):
    """
    CRITICAL FIX: Returns a JSON response containing the payment_id to the client-side 
    JavaScript to initiate the polling loop.
    """
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        
        # 1. Get ACTIVE cart and calculate total
        try:
            cart = Cart.objects.get(user=request.user, is_active=True)
            amount = int(cart.total_price())
            
            # CRITICAL: For M-Pesa Sandbox testing, the minimum amount is typically 1 KES
            api_amount = 1 if amount <= 0 else amount
            
            if amount <= 0:
                return JsonResponse({'success': False, 'error': 'Your cart is empty'}, status=400)
                
        except Cart.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Cart not found'}, status=404)
        
        # 2. Format phone number (remove leading 0, add 254)
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif not phone_number.startswith('254'):
            phone_number = '254' + phone_number
        
        # 3. Get access token
        access_token = get_mpesa_access_token()
        if not access_token:
            return JsonResponse({'success': False, 'error': 'Failed to authenticate with M-Pesa'}, status=500)
        
        # 4. Prepare STK Push request
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
            "Amount": api_amount, # Use the sandbox-safe amount
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
                # 5. Save payment record
                payment = MpesaPayment.objects.create(
                    user=request.user,
                    phone_number=phone_number,
                    amount=amount, # Store the actual cart amount
                    merchant_request_id=response_data.get('MerchantRequestID'),
                    checkout_request_id=response_data.get('CheckoutRequestID'),
                    status='pending'
                )
                
                # Store cart ID in session for later reference (for confirmation page)
                request.session['pending_cart_id'] = cart.id
                
                # 6. Return JSON SUCCESS to the client to start polling
                return JsonResponse({
                    'success': True,
                    'payment_id': payment.id,
                    'message': 'STK Push sent successfully. Awaiting PIN.'
                })
            else:
                error_message = response_data.get('errorMessage', response_data.get('ResponseDescription', 'Payment request failed'))
                logger.error(f"STK Push failed for user {request.user.id}: {error_message}")
                return JsonResponse({'success': False, 'error': error_message}, status=500)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"STK Push Request Error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Failed to communicate with M-Pesa API.'}, status=500)
            
        except Exception as e:
            logger.error(f"STK Push Internal Error: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Failed to initiate payment. Please try again.'}, status=500)
    
    # GET request - return JSON error (frontend should only call via POST)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@csrf_exempt
def mpesa_callback(request):
    """
    Handle M-Pesa callback after payment. Called ONLY by the Daraja API.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            stk_callback = data.get('Body', {}).get('stkCallback', {})
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc', 'No description provided.')
            
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
                            # Safaricom format is YYYYMMDDHHmmss
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
                        logger.info(f"Cart {cart.id} marked as inactive after successful payment.")
                    except Cart.DoesNotExist:
                        logger.warning(f"No active cart found for user {payment.user.id} during successful callback.")
                        
                else:
                    # Payment failed/cancelled
                    payment.status = 'failed'
                
                payment.save()
                
            except MpesaPayment.DoesNotExist:
                logger.error(f"Payment not found for checkout request: {checkout_request_id}")
            
            # Must return success acknowledgement to M-Pesa API
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
            
        except Exception as e:
            logger.critical(f"Callback Processing Error: {str(e)} - Raw Data: {request.body}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Failed'})
    
    return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid request'})


@login_required
def payment_confirmation(request, payment_id):
    """Show payment confirmation/receipt page (HTML template)"""
    payment = get_object_or_404(MpesaPayment, id=payment_id, user=request.user)
    
    # Logic to fetch cart items for display (remains the same as your original)
    cart_id = request.session.get('pending_cart_id')
    cart_items = []
    
    if cart_id:
        try:
            cart = Cart.objects.get(id=cart_id)
            cart_items = CartItem.objects.filter(cart=cart)
        except Cart.DoesNotExist:
            pass
    # ... (rest of the cart fetching logic remains the same) ...
    
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
        'payment': payment,
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
    """
    CRITICAL FIX: AJAX endpoint to check payment status. Returns current status 
    to drive the frontend polling and transitions.
    """
    try:
        payment = MpesaPayment.objects.get(id=payment_id, user=request.user)
        
        # NOTE: The cart is officially marked inactive in mpesa_callback. 
        # We just report the payment status here.
        
        return JsonResponse({
            'status': payment.status,
            'result_desc': payment.result_desc,
            'mpesa_receipt': payment.mpesa_receipt_number,
            'should_refresh': payment.status in ['completed', 'failed', 'cancelled']
        })
    except MpesaPayment.DoesNotExist:
        return JsonResponse({'error': 'Payment not found'}, status=404)


@login_required
def payment_status(request, payment_id):
    """Redirect for compatibility."""
    return redirect('payments:payment_confirmation', payment_id=payment_id)