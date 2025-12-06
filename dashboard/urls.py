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