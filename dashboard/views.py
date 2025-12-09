
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from foods.models import Food
from django.db.models import Count, Q
import json
from django.contrib.auth.models import User 
from datetime import datetime
from foods.models import Cart
from foods.models import CartItem


# Check if user is staff/admin
def is_staff_user(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_staff_user)
def dashboard_home(request):
    """Main dashboard view with statistics"""
    foods = Food.objects.all().order_by('-id')
    
    # Calculate statistics
    total_foods = foods.count()
    available_foods = foods.filter(available=True).count()
    out_of_stock = foods.filter(available=False).count()
    
    
    total_categories = foods.values('category').distinct().count()
    
    context = {
        'foods': foods,
        'total_foods': total_foods,
        'available_foods': available_foods,
        'out_of_stock': out_of_stock,
        'total_categories': total_categories,
    }
    
    return render(request, 'dashboard/home.html', context)


@login_required
@user_passes_test(is_staff_user)
def manage_foods(request):
    """View all foods (alternative to dashboard_home)"""
    foods = Food.objects.all().order_by('-id')
    return render(request, 'dashboard/manage_foods.html', {'foods': foods})


@login_required
@user_passes_test(is_staff_user)
def add_food(request):
    """Add new food item"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        category = request.POST.get('category')
        available = request.POST.get('available') == 'on'
        image = request.FILES.get('image')
        
        # Validate required fields
        if not name or not price:
            messages.error(request, 'Name and price are required.')
            return render(request, 'dashboard/add_food.html')
        
        try:
            # Create new food item
            food = Food.objects.create(
                name=name,
                description=description,
                price=price,
                category=category,
                available=available,
                image=image
            )
            
            messages.success(request, f'{food.name} has been added successfully!')
            return redirect('dashboard:dashboard_home')
        
        except Exception as e:
            messages.error(request, f'Error adding food: {str(e)}')
            return render(request, 'dashboard/add_food.html')
    
    return render(request, 'dashboard/add_food.html')


@login_required
@user_passes_test(is_staff_user)
def edit_food(request, food_id):
    """Edit existing food item"""
    food = get_object_or_404(Food, id=food_id)
    
    if request.method == 'POST':
        food.name = request.POST.get('name')
        food.description = request.POST.get('description')
        food.price = request.POST.get('price')
        food.category = request.POST.get('category')
        food.available = request.POST.get('available') == 'on'
        
        # Handle image upload
        if request.FILES.get('image'):
            food.image = request.FILES.get('image')
        
        try:
            food.save()
            messages.success(request, f'{food.name} has been updated successfully!')
            return redirect('dashboard:dashboard_home')
        
        except Exception as e:
            messages.error(request, f'Error updating food: {str(e)}')
    
    return render(request, 'dashboard/edit_food.html', {'food': food})


@login_required
@user_passes_test(is_staff_user)
def delete_food(request, food_id):
    """Delete food item - now with AJAX support"""
    food = get_object_or_404(Food, id=food_id)
    
    if request.method == 'POST':
        food_name = food.name
        
        try:
            food.delete()
            
            # Return JSON for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': f'{food_name} has been deleted successfully!'
                })
            
            messages.success(request, f'{food_name} has been deleted successfully!')
        
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': False, 'message': str(e)})
            messages.error(request, f'Error deleting food: {str(e)}')
    
    return redirect('dashboard:dashboard_home')


@login_required
@user_passes_test(is_staff_user)
@require_POST
def toggle_availability(request, food_id):
    """Toggle food availability status via AJAX"""
    try:
        food = get_object_or_404(Food, id=food_id)
        data = json.loads(request.body)
        food.available = data.get('available', False)
        food.save()
        
        return JsonResponse({
            'success': True,
            'food_name': food.name,
            'available': food.available
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@user_passes_test(is_staff_user)
@require_POST
def update_price(request, food_id):
    """Update food price via AJAX"""
    try:
        food = get_object_or_404(Food, id=food_id)
        data = json.loads(request.body)
        new_price = float(data.get('price', 0))
        
        if new_price < 0:
            return JsonResponse({'success': False, 'message': 'Price cannot be negative'}, status=400)
        
        food.price = new_price
        food.save()
        
        return JsonResponse({
            'success': True,
            'food_name': food.name,
            'new_price': float(food.price)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@user_passes_test(is_staff_user)
def print_report(request):
    """Generate printable report"""
    
    # Get all statistics
    total_foods = Food.objects.count()
    available_foods = Food.objects.filter(available=True).count()
    out_of_stock = Food.objects.filter(available=False).count()
    total_users = User.objects.filter(is_staff=False).count()
    
    # Get all foods
    foods = Food.objects.all().order_by('-id')
    
    # Get cart statistics
    total_carts = Cart.objects.count()
    total_cart_items = CartItem.objects.count()
    
    context = {
        'total_foods': total_foods,
        'available_foods': available_foods,
        'out_of_stock': out_of_stock,
        'total_users': total_users,
        'total_carts': total_carts,
        'total_cart_items': total_cart_items,
        'foods': foods,
        'report_date': datetime.now(),
    }
    
    return render(request, 'dashboard/print_report.html', context)

