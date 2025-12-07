from django.contrib.auth.models import User
from django.db import models

class Food(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=6, decimal_places=2)
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


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    is_active = models.BooleanField(default=True)  # Track active/inactive carts
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart ({self.user}) - {'Active' if self.is_active else 'Completed'}"

    def total_price(self):
        return sum(item.total_price() for item in self.items.all())
    
    class Meta:
        ordering = ['-created_at']


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    food = models.ForeignKey('Food', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_price(self):
        return self.food.price * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.food.name}"
    
    class Meta:
        ordering = ['created_at']