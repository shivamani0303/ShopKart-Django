def cart_context(request):
    cart = request.session.get("cart", {})
    cart_count = sum(int(item.get("quantity", 0)) for item in cart.values())
    return {
        "cart_count": cart_count,
    }
