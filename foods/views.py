# foods/views.py - Complete Updated Version

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Food, Cart, CartItem


def landing_page(request):
    """Public landing page - no login required"""
    return render(request, 'base.html')


@login_required
def home(request):
    """Food ordering page - login required"""
    foods = Food.objects.filter(available=True)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        foods = foods.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Category filter
    category = request.GET.get('category', '')
    if category:
        foods = foods.filter(category__iexact=category)
    
    foods = foods.order_by('-id')
    
    return render(request, 'foods/home.html', {
        'foods': foods,
        'search_query': search_query,
        'selected_category': category,
    })


def product_list(request):
    """Redirect to home (for backward compatibility)"""
    if request.user.is_authenticated:
        return redirect('food_ordering')
    return redirect('landing_page')


@login_required
def add_to_cart(request, food_id):
    """Add food item to cart"""
    food = get_object_or_404(Food, id=food_id)
    
    # Check if food is available
    if not food.available:
        messages.error(request, f'{food.name} is currently out of stock.')
        return redirect('food_ordering')
    
    # Get or create ACTIVE cart for user
    cart, created = Cart.objects.get_or_create(
        user=request.user,
        is_active=True
    )
    
    # Get or create cart item
    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart,
        food=food,
        defaults={'quantity': 1}
    )

    if not item_created:
        cart_item.quantity += 1
        cart_item.save()
        messages.success(request, f'{food.name} quantity updated in cart!')
    else:
        messages.success(request, f'{food.name} added to cart!')

    return redirect('view_cart')


@login_required
def update_cart_item(request, item_id):
    """Update cart item quantity"""
    if request.method == 'POST':
        item = get_object_or_404(CartItem, id=item_id, cart__user=request.user, cart__is_active=True)
        quantity = int(request.POST.get('quantity', 1))
        
        if quantity > 0:
            item.quantity = quantity
            item.save()
            messages.success(request, f'{item.food.name} quantity updated!')
        else:
            messages.error(request, 'Quantity must be at least 1.')
    
    return redirect('view_cart')


@login_required
def remove_from_cart(request, item_id):
    """Remove item from cart"""
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user, cart__is_active=True)
    food_name = item.food.name
    item.delete()
    messages.success(request, f'{food_name} removed from cart.')
    return redirect('view_cart')


@login_required
def view_cart(request):
    """Display cart with all items"""
    # Get or create ACTIVE cart
    cart, created = Cart.objects.get_or_create(
        user=request.user,
        is_active=True
    )
    
    # Get all items in the active cart
    cart_items = CartItem.objects.filter(cart=cart).select_related('food')
    total_amount = sum(item.total_price() for item in cart_items)
    
    return render(request, 'foods/cart.html', {
        'cart': cart,
        'cart_items': cart_items,
        'total_amount': total_amount
    })


@login_required
def clear_cart(request):
    """Clear all items from active cart"""
    try:
        cart = Cart.objects.get(user=request.user, is_active=True)
        cart.items.all().delete()
        messages.success(request, 'Cart cleared successfully!')
    except Cart.DoesNotExist:
        messages.info(request, 'Cart is already empty.')
    
    return redirect('view_cart')