from django import forms
from foods.models import Food  # Make sure you have a Food model in foods app

class FoodForm(forms.ModelForm):
    class Meta:
        model = Food
        fields = ['name', 'description', 'price', 'image']  # Adjust fields as needed
