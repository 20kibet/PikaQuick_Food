def cart_count(request):
    """
    Context processor to add cart item count to all templates.
    Returns the number of items in the user's cart.
    """
    if request.user.is_authenticated:
        try:
            from .models import Cart
            cart_items = Cart.objects.filter(user=request.user)
            count = sum(item.quantity for item in cart_items)
            return {'cart_count': count}
        except Exception:
            return {'cart_count': 0}
    return {'cart_count': 0}