# foods/urls.py - Updated URL Configuration

from django.urls import path
from . import views

urlpatterns = [
    # Landing page (public)
    path('', views.landing_page, name='landing_page'),
    
    # Food ordering page (requires login)
    path('order/', views.home, name='food_ordering'),
    
    # Legacy URL (redirects to appropriate page)
    path('home/', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    
    # Cart operations
    path('cart/', views.view_cart, name='view_cart'),
    path('add-to-cart/<int:food_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
]