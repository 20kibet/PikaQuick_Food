from django.shortcuts import render
from .models import Food, Cart, CartItem
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

def home(request):
    # Get some featured foods for the homepage
    foods = Food.objects.all()[:8]  # Get first 8 foods for display
    return render(request, 'foods/home.html', {'foods': foods})  # Changed from base.html

def product_list(request):
    foods = Food.objects.all()
    return render(request, 'foods/product_list.html', {'foods': foods})

@login_required
def add_to_cart(request, food_id):
    food = get_object_or_404(Food, id=food_id)
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, food=food)

    if not created:
        cart_item.quantity += 1
        cart_item.save()

    return redirect('view_cart')

@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id)
    item.delete()
    return redirect('view_cart')

@login_required
def view_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = CartItem.objects.filter(cart=cart)
    total_amount = sum(item.food.price * item.quantity for item in cart_items)
    
    return render(request, 'foods/cart.html', {
        'cart': cart,
        'cart_items': cart_items,
        'total_amount': total_amount
    })