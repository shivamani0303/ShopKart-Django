from decimal import Decimal
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CheckoutForm, ProfileForm, RegisterForm
from .models import Category, Order, OrderItem, Product, Wishlist


def home(request):
    # 8 featured products — one per category where possible
    products = Product.objects.filter(is_active=True).select_related("category").order_by("-created_at")[:8]
    categories = Category.objects.all().order_by("name")
    return render(request, "shop/home.html", {"products": products, "categories": categories})


def product_list(request):
    qs = Product.objects.filter(is_active=True).select_related("category")
    categories = Category.objects.all()

    q = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    sort = request.GET.get("sort", "").strip()

    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(category__name__icontains=q)
        )
    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    sort_map = {
        "price_asc":  "price",
        "price_desc": "-price",
        "name_asc":   "name",
        "newest":     "-created_at",
    }
    qs = qs.order_by(sort_map.get(sort, "-created_at"))

    paginator = Paginator(qs, 24)          # 24 products per page (4×6 grid)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    sort_options = [
        ("newest",     "Newest First"),
        ("price_asc",  "Price: Low to High"),
        ("price_desc", "Price: High to Low"),
        ("name_asc",   "Name: A–Z"),
    ]

    return render(
        request,
        "shop/product_list.html",
        {
            "products": page_obj,
            "page_obj": page_obj,
            "total_count": paginator.count,
            "categories": categories,
            "q": q,
            "sort": sort,
            "sort_options": sort_options,
            "selected_category": category_slug,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    related = Product.objects.filter(
        category=product.category, is_active=True
    ).exclude(pk=product.pk)[:4]
    wished = (
        request.user.is_authenticated
        and Wishlist.objects.filter(user=request.user, product=product).exists()
    )
    return render(
        request,
        "shop/product_detail.html",
        {"product": product, "related": related, "wished": wished},
    )


def _cart_data(request):
    cart = request.session.get("cart", {})
    products = Product.objects.filter(pk__in=cart.keys(), is_active=True)
    product_map = {str(p.pk): p for p in products}
    items = []
    total = Decimal("0.00")

    for product_id, data in cart.items():
        product = product_map.get(str(product_id))
        if not product:
            continue
        quantity = max(1, int(data.get("quantity", 1)))
        subtotal = product.price * quantity
        total += subtotal
        items.append({
            "product": product,
            "quantity": quantity,
            "subtotal": subtotal,
        })
    return items, total


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    if product.stock < 1:
        messages.error(request, "This product is currently out of stock.")
        return redirect("shop:product_detail", product.slug)

    cart = request.session.get("cart", {})
    key = str(product.id)
    current = int(cart.get(key, {}).get("quantity", 0))
    if current >= product.stock:
        messages.warning(request, "You cannot add more than the available stock.")
    else:
        cart[key] = {"quantity": current + 1}
        request.session["cart"] = cart
        request.session.modified = True
        messages.success(request, f"{product.name} added to cart.")
    return redirect(request.POST.get("next") or "shop:cart")


@require_POST
def cart_update(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    quantity = max(0, int(request.POST.get("quantity", 1)))
    cart = request.session.get("cart", {})
    key = str(product.id)

    if quantity == 0:
        cart.pop(key, None)
    else:
        cart[key] = {"quantity": min(quantity, product.stock)}

    request.session["cart"] = cart
    request.session.modified = True
    messages.success(request, "Cart updated.")
    return redirect("shop:cart")


@require_POST
def cart_remove(request, product_id):
    cart = request.session.get("cart", {})
    cart.pop(str(product_id), None)
    request.session["cart"] = cart
    request.session.modified = True
    messages.success(request, "Item removed from cart.")
    return redirect("shop:cart")


def cart(request):
    items, total = _cart_data(request)
    return render(request, "shop/cart.html", {"items": items, "total": total})


def register(request):
    if request.user.is_authenticated:
        return redirect("shop:home")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully.")
            return redirect("shop:home")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


@login_required
def checkout(request):
    items, total = _cart_data(request)
    if not items:
        messages.warning(request, "Your cart is empty.")
        return redirect("shop:product_list")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                locked_products = {
                    p.id: p
                    for p in Product.objects.select_for_update().filter(
                        id__in=[item["product"].id for item in items]
                    )
                }

                for item in items:
                    product = locked_products[item["product"].id]
                    if item["quantity"] > product.stock:
                        messages.error(
                            request,
                            f"Only {product.stock} units of {product.name} are available."
                        )
                        return redirect("shop:cart")

                order = form.save(commit=False)
                order.user = request.user
                order.order_number = f"ORD-{uuid.uuid4().hex[:10].upper()}"
                order.total_amount = total
                order.save()

                for item in items:
                    product = locked_products[item["product"].id]
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        product_name=product.name,
                        price=product.price,
                        quantity=item["quantity"],
                    )
                    product.stock -= item["quantity"]
                    product.save(update_fields=["stock"])

                request.session["cart"] = {}
                request.session.modified = True

            if order.payment_method == "RAZORPAY" and settings.RAZORPAY_KEY_ID:
                return redirect("shop:payment", order_id=order.id)

            if order.payment_method == "RAZORPAY":
                messages.warning(
                    request,
                    "Razorpay keys are not configured, so the order was created as pending payment."
                )
            else:
                order.payment_status = "COD_PENDING"
                order.save(update_fields=["payment_status"])

            messages.success(request, f"Order {order.order_number} placed successfully.")
            return redirect("shop:order_detail", order_id=order.id)
    else:
        initial = {
            "full_name": request.user.get_full_name(),
            "email": request.user.email,
        }
        form = CheckoutForm(initial=initial)

    return render(
        request,
        "shop/checkout.html",
        {"form": form, "items": items, "total": total},
    )


@login_required
def orders(request):
    user_orders = Order.objects.filter(user=request.user).prefetch_related("items")
    return render(request, "shop/orders.html", {"orders": user_orders})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        pk=order_id,
        user=request.user,
    )
    return render(request, "shop/order_detail.html", {"order": order})


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("shop:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "shop/profile.html", {"form": form})


@login_required
@require_POST
def wishlist_toggle(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if created:
        messages.success(request, f"{product.name} added to wishlist.")
    else:
        item.delete()
        messages.info(request, f"{product.name} removed from wishlist.")
    return redirect(request.POST.get("next") or product.get_absolute_url())


@login_required
def wishlist(request):
    items = Wishlist.objects.filter(user=request.user).select_related("product", "product__category")
    return render(request, "shop/wishlist.html", {"items": items})


@login_required
def payment(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)

    if order.payment_method != "RAZORPAY":
        return redirect("shop:order_detail", order_id=order.id)

    # Already paid — send straight to order detail
    if order.payment_status == "PAID":
        messages.info(request, "This order has already been paid.")
        return redirect("shop:order_detail", order_id=order.id)

    razorpay_order_id = order.razorpay_order_id  # may be empty string on first visit
    payment_enabled = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)

    if payment_enabled:
        try:
            import razorpay
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            # Reuse an existing Razorpay order_id so we don't create duplicates
            # on page refresh — only call the API when there's no stored id yet.
            if order.razorpay_order_id:
                razorpay_order_id = order.razorpay_order_id
            else:
                amount_paise = int(order.total_amount * 100)
                if amount_paise < 100:
                    raise ValueError(
                        f"Order amount ₹{order.total_amount} is below the minimum of ₹1."
                    )
                rp_order = client.order.create({
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": order.order_number,
                    "notes": {
                        "order_number": order.order_number,
                        "customer": order.full_name,
                    },
                })
                razorpay_order_id = rp_order["id"]
                # Persist so page refreshes don't create duplicate Razorpay orders
                order.razorpay_order_id = razorpay_order_id
                order.save(update_fields=["razorpay_order_id", "updated_at"])
        except Exception as exc:
            messages.error(request, f"Payment gateway could not be initialized: {exc}")
            payment_enabled = False

    return render(
        request,
        "shop/payment.html",
        {
            "order": order,
            "razorpay_order_id": razorpay_order_id,
            "payment_enabled": payment_enabled,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
            "payment_amount_paise": int(order.total_amount * 100),
        },
    )


@login_required
@require_POST
def payment_success(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    payment_id = request.POST.get("payment_id", "").strip()
    razorpay_order_id = request.POST.get("razorpay_order_id", "").strip()
    signature = request.POST.get("signature", "").strip()

    if not (payment_id and razorpay_order_id and signature):
        messages.error(request, "Payment verification data was missing.")
        return redirect("shop:payment", order_id=order.id)

    if not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET):
        messages.error(request, "Razorpay is not configured.")
        return redirect("shop:payment", order_id=order.id)

    try:
        import razorpay
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        client.utility.verify_payment_signature({
            "razorpay_order_id":   razorpay_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature":  signature,
        })
    except Exception:
        messages.error(request, "Payment signature verification failed. Please contact support.")
        return redirect("shop:payment", order_id=order.id)

    # Signature valid — mark order as paid and persist all Razorpay IDs
    order.payment_id         = payment_id
    order.razorpay_order_id  = razorpay_order_id
    order.razorpay_signature = signature
    order.payment_status     = "PAID"
    order.status             = "CONFIRMED"
    order.save(update_fields=[
        "payment_id", "razorpay_order_id", "razorpay_signature",
        "payment_status", "status", "updated_at",
    ])
    messages.success(request, "Payment successful! Your order is confirmed.")
    return redirect("shop:order_detail", order_id=order.id)
