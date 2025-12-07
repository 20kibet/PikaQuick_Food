
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from foods.models import Food
from django.db.models import Count, Q
import json

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
    
    # Get unique categories (assuming you have a category field)
    # If not, this will return 0
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


# ============================================
# Dashboard/urls.py - Updated with AJAX endpoints
# ============================================

"""
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='dashboard_home'),
    path('manage/', views.manage_foods, name='manage_foods'),
    path('add/', views.add_food, name='add_food'),
    path('edit/<int:food_id>/', views.edit_food, name='edit_food'),
    path('delete/<int:food_id>/', views.delete_food, name='delete_food'),
    
    # AJAX endpoints
    path('toggle-availability/<int:food_id>/', views.toggle_availability, name='toggle_availability'),
    path('update-price/<int:food_id>/', views.update_price, name='update_price'),
]
"""


# ============================================
# Foods/models.py - Make sure your Food model has these fields
# ============================================

"""
from django.db import models

class Food(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to='foods/', blank=True, null=True)
    available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Foods'
"""


# ============================================
# pikaquick/settings.py - Add media files configuration
# ============================================

"""
import os

# Media files (uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
"""


# ============================================
# pikaquick/urls.py - Add media files serving
# ============================================

"""
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ... your existing urls
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
"""


# ============================================
# IMPORTANT: Install Pillow for image handling
# ============================================

"""
pip install Pillow
"""