def cart_count(request):
    """
    Context processor to add cart item count to all templates.
    Returns the number of items in the user's cart.
    """
    if request.user.is_authenticated:
        try:
            from .models import Cart, CartItem
            cart = Cart.objects.filter(user=request.user).first()
            if cart:
                count = CartItem.objects.filter(cart=cart).count()
                return {'cart_count': count}
        except Exception:
            return {'cart_count': 0}
    return {'cart_count': 0}