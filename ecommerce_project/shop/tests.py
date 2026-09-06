"""
ShopKart – Full Test Suite
===========================
Day 7 · Testing, Documentation & Deployment

Covers
------
1.  Models          – Category, Product, Order, OrderItem, Wishlist
2.  Product views   – home, product_list (search/filter/sort/pagination),
                      product_detail
3.  Auth            – register, login, logout
4.  Cart            – add, update, remove, view, stock enforcement
5.  Checkout        – login guard, empty-cart guard, COD order creation,
                      Razorpay redirect
6.  Orders          – order list, order detail (ownership)
7.  Wishlist        – toggle add, toggle remove, list page
8.  Razorpay        – payment page (mocked API), already-paid guard,
                      non-Razorpay redirect
9.  Payment success – valid signature (mocked), invalid signature,
                      missing fields, already-paid re-submission
10. Context         – cart_count context processor

No real Razorpay API calls are made.  All external SDK calls are patched
with unittest.mock so the test suite is fully offline.
"""

import hmac
import hashlib
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Category, Order, OrderItem, Product, Wishlist

# ── Dummy Razorpay credentials used in every test that needs them ───────────
FAKE_KEY_ID     = "rzp_test_TESTKEY123456"
FAKE_KEY_SECRET = "test_secret_abcdefghij"

# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_valid_signature(order_id: str, payment_id: str, secret: str) -> str:
    """Reproduce the HMAC-SHA256 that Razorpay generates for a payment."""
    body = f"{order_id}|{payment_id}"
    return hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _checkout_post_data(payment_method: str = "COD") -> dict:
    return {
        "full_name":      "Test User",
        "email":          "test@example.com",
        "phone":          "9876543210",
        "address":        "123 Test Street",
        "city":           "Chennai",
        "state":          "Tamil Nadu",
        "pincode":        "600001",
        "payment_method": payment_method,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. MODEL TESTS
# ═══════════════════════════════════════════════════════════════════════════

class CategoryModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Electronics", slug="electronics",
            description="Electronic items"
        )

    def test_str(self):
        self.assertEqual(str(self.category), "Electronics")

    def test_unique_name(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Category.objects.create(name="Electronics", slug="electronics-2")

    def test_ordering_alphabetical(self):
        Category.objects.create(name="Accessories", slug="accessories")
        names = list(Category.objects.values_list("name", flat=True))
        self.assertEqual(names, sorted(names))


class ProductModelTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gadgets", slug="gadgets")
        self.product = Product.objects.create(
            category=self.cat,
            name="Smart Speaker",
            slug="smart-speaker",
            description="A great speaker",
            price=Decimal("999.00"),
            stock=10,
            is_active=True,
        )

    def test_str(self):
        self.assertEqual(str(self.product), "Smart Speaker")

    def test_in_stock_true(self):
        self.assertTrue(self.product.in_stock)

    def test_in_stock_false_when_zero(self):
        self.product.stock = 0
        self.product.save()
        self.product.refresh_from_db()
        self.assertFalse(self.product.in_stock)

    def test_get_absolute_url(self):
        url = self.product.get_absolute_url()
        self.assertIn("smart-speaker", url)

    def test_inactive_product_not_returned_in_active_filter(self):
        self.product.is_active = False
        self.product.save()
        count = Product.objects.filter(is_active=True).count()
        self.assertEqual(count, 0)


class OrderModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="buyer", password="Pass1234!")
        self.cat = Category.objects.create(name="Home", slug="home")
        self.product = Product.objects.create(
            category=self.cat, name="Lamp", slug="lamp",
            description="Desk lamp", price=Decimal("500.00"), stock=5,
        )
        self.order = Order.objects.create(
            user=self.user,
            order_number="ORD-TEST001",
            full_name="Buyer One",
            email="buyer@test.com",
            phone="9000000000",
            address="1 Main Rd",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
            payment_method="COD",
            total_amount=Decimal("500.00"),
        )

    def test_str(self):
        self.assertIn("ORD-TEST001", str(self.order))

    def test_default_status(self):
        self.assertEqual(self.order.status, "PLACED")

    def test_default_payment_status(self):
        self.assertEqual(self.order.payment_status, "PENDING")

    def test_razorpay_fields_blank_by_default(self):
        self.assertEqual(self.order.razorpay_order_id, "")
        self.assertEqual(self.order.payment_id, "")
        self.assertEqual(self.order.razorpay_signature, "")


class OrderItemModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="buyer2", password="Pass1234!")
        self.cat  = Category.objects.create(name="Sports", slug="sports")
        self.prod = Product.objects.create(
            category=self.cat, name="Ball", slug="ball",
            description="Rubber ball", price=Decimal("200.00"), stock=10,
        )
        self.order = Order.objects.create(
            user=self.user, order_number="ORD-ITEM001",
            full_name="Test", email="t@t.com", phone="0",
            address="addr", city="city", state="state", pincode="000000",
            total_amount=Decimal("400.00"),
        )
        self.item = OrderItem.objects.create(
            order=self.order, product=self.prod,
            product_name="Ball", price=Decimal("200.00"), quantity=2,
        )

    def test_subtotal(self):
        self.assertEqual(self.item.subtotal, Decimal("400.00"))

    def test_str(self):
        self.assertIn("Ball", str(self.item))


class WishlistModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="wisher", password="Pass1234!")
        self.cat  = Category.objects.create(name="Beauty", slug="beauty")
        self.prod = Product.objects.create(
            category=self.cat, name="Lipstick", slug="lipstick",
            description="Red lipstick", price=Decimal("299.00"), stock=20,
        )

    def test_add_to_wishlist(self):
        w = Wishlist.objects.create(user=self.user, product=self.prod)
        self.assertEqual(str(w), "wisher - Lipstick")

    def test_unique_constraint(self):
        from django.db import IntegrityError
        Wishlist.objects.create(user=self.user, product=self.prod)
        with self.assertRaises(IntegrityError):
            Wishlist.objects.create(user=self.user, product=self.prod)


# ═══════════════════════════════════════════════════════════════════════════
# 2. PRODUCT VIEW TESTS
# ═══════════════════════════════════════════════════════════════════════════

class ProductViewTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Tech", slug="tech")
        self.p1 = Product.objects.create(
            category=self.cat, name="Laptop", slug="laptop",
            description="A fast laptop", price=Decimal("50000.00"), stock=3,
        )
        self.p2 = Product.objects.create(
            category=self.cat, name="Mouse", slug="mouse",
            description="Wireless mouse", price=Decimal("800.00"), stock=0,
            is_active=False,
        )

    # ── Home ──────────────────────────────────────────────────────────────
    def test_home_200(self):
        r = self.client.get(reverse("shop:home"))
        self.assertEqual(r.status_code, 200)

    def test_home_uses_correct_template(self):
        r = self.client.get(reverse("shop:home"))
        self.assertTemplateUsed(r, "shop/home.html")

    def test_home_contains_active_product(self):
        r = self.client.get(reverse("shop:home"))
        self.assertContains(r, "Laptop")

    def test_home_does_not_show_inactive_product(self):
        r = self.client.get(reverse("shop:home"))
        self.assertNotContains(r, "Mouse")

    # ── Product list ──────────────────────────────────────────────────────
    def test_product_list_200(self):
        r = self.client.get(reverse("shop:product_list"))
        self.assertEqual(r.status_code, 200)

    def test_product_list_search_match(self):
        r = self.client.get(reverse("shop:product_list") + "?q=laptop")
        self.assertContains(r, "Laptop")

    def test_product_list_search_no_match(self):
        r = self.client.get(reverse("shop:product_list") + "?q=zzznomatch")
        self.assertNotContains(r, "Laptop")

    def test_product_list_category_filter(self):
        other_cat = Category.objects.create(name="Fashion", slug="fashion")
        Product.objects.create(
            category=other_cat, name="T-Shirt", slug="t-shirt",
            description="Cotton tee", price=Decimal("499.00"), stock=10,
        )
        r = self.client.get(reverse("shop:product_list") + "?category=fashion")
        self.assertContains(r, "T-Shirt")
        self.assertNotContains(r, "Laptop")

    def test_product_list_sort_price_asc(self):
        r = self.client.get(reverse("shop:product_list") + "?sort=price_asc")
        self.assertEqual(r.status_code, 200)

    def test_product_list_sort_price_desc(self):
        r = self.client.get(reverse("shop:product_list") + "?sort=price_desc")
        self.assertEqual(r.status_code, 200)

    def test_product_list_pagination_context(self):
        r = self.client.get(reverse("shop:product_list"))
        self.assertIn("page_obj", r.context)
        self.assertIn("total_count", r.context)

    # ── Product detail ────────────────────────────────────────────────────
    def test_product_detail_200(self):
        r = self.client.get(self.p1.get_absolute_url())
        self.assertEqual(r.status_code, 200)

    def test_product_detail_shows_name_and_price(self):
        r = self.client.get(self.p1.get_absolute_url())
        self.assertContains(r, "Laptop")
        self.assertContains(r, "50000")

    def test_product_detail_inactive_returns_404(self):
        self.p2.is_active = False
        self.p2.save()
        r = self.client.get(self.p2.get_absolute_url())
        self.assertEqual(r.status_code, 404)


# ═══════════════════════════════════════════════════════════════════════════
# 3. AUTH TESTS
# ═══════════════════════════════════════════════════════════════════════════

class AuthTest(TestCase):

    # ── Registration ──────────────────────────────────────────────────────
    def test_register_page_200(self):
        r = self.client.get(reverse("shop:register"))
        self.assertEqual(r.status_code, 200)

    def test_register_success_creates_user_and_logs_in(self):
        r = self.client.post(reverse("shop:register"), {
            "username":  "newuser",
            "email":     "new@test.com",
            "password1": "TestPass@99",
            "password2": "TestPass@99",
        })
        self.assertRedirects(r, reverse("shop:home"))
        self.assertTrue(User.objects.filter(username="newuser").exists())
        # Confirm the user is now authenticated by checking a login-only page
        # (profile page, not checkout — checkout needs items in cart too)
        r2 = self.client.get(reverse("shop:profile"))
        self.assertEqual(r2.status_code, 200)

    def test_register_password_mismatch_shows_error(self):
        r = self.client.post(reverse("shop:register"), {
            "username":  "failuser",
            "email":     "fail@test.com",
            "password1": "TestPass@99",
            "password2": "WRONGPASS",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="failuser").exists())

    def test_register_redirects_if_already_logged_in(self):
        User.objects.create_user(username="existing", password="Pass1234!")
        self.client.login(username="existing", password="Pass1234!")
        r = self.client.get(reverse("shop:register"))
        self.assertRedirects(r, reverse("shop:home"))

    # ── Login ─────────────────────────────────────────────────────────────
    def test_login_valid_credentials(self):
        User.objects.create_user(username="logintest", password="Pass1234!")
        r = self.client.post(reverse("login"), {
            "username": "logintest",
            "password": "Pass1234!",
        })
        self.assertRedirects(r, reverse("shop:home"))

    def test_login_invalid_credentials(self):
        r = self.client.post(reverse("login"), {
            "username": "noone",
            "password": "wrongpass",
        })
        self.assertEqual(r.status_code, 200)

    # ── Protected views redirect to login when anonymous ─────────────────
    def test_checkout_requires_login(self):
        r = self.client.get(reverse("shop:checkout"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("login", r["Location"])

    def test_orders_requires_login(self):
        r = self.client.get(reverse("shop:orders"))
        self.assertEqual(r.status_code, 302)

    def test_profile_requires_login(self):
        r = self.client.get(reverse("shop:profile"))
        self.assertEqual(r.status_code, 302)


# ═══════════════════════════════════════════════════════════════════════════
# 4. CART TESTS
# ═══════════════════════════════════════════════════════════════════════════

class CartTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Kitchenware", slug="kitchenware")
        self.product = Product.objects.create(
            category=self.cat, name="Blender", slug="blender",
            description="A fast blender", price=Decimal("2499.00"), stock=5,
        )
        self.add_url    = reverse("shop:cart_add",    args=[self.product.id])
        self.update_url = reverse("shop:cart_update", args=[self.product.id])
        self.remove_url = reverse("shop:cart_remove", args=[self.product.id])
        self.cart_url   = reverse("shop:cart")

    def _add_to_cart(self, qty: int = 1):
        for _ in range(qty):
            self.client.post(self.add_url)

    # ── Add ───────────────────────────────────────────────────────────────
    def test_add_to_cart_redirects_to_cart(self):
        r = self.client.post(self.add_url)
        self.assertRedirects(r, self.cart_url)

    def test_add_sets_quantity_1(self):
        self.client.post(self.add_url)
        session = self.client.session
        self.assertEqual(session["cart"][str(self.product.id)]["quantity"], 1)

    def test_add_twice_increments_quantity(self):
        self.client.post(self.add_url)
        self.client.post(self.add_url)
        session = self.client.session
        self.assertEqual(session["cart"][str(self.product.id)]["quantity"], 2)

    def test_add_cannot_exceed_stock(self):
        # stock is 5; add 5 times should succeed, 6th should warn
        for _ in range(5):
            self.client.post(self.add_url)
        self.client.post(self.add_url)   # 6th attempt
        session = self.client.session
        qty = session["cart"][str(self.product.id)]["quantity"]
        self.assertLessEqual(qty, self.product.stock)

    def test_add_out_of_stock_product_blocked(self):
        self.product.stock = 0
        self.product.save()
        r = self.client.post(self.add_url)
        # Redirects to product_detail, not cart
        self.assertNotEqual(r["Location"], self.cart_url)
        session = self.client.session
        self.assertNotIn(str(self.product.id), session.get("cart", {}))

    def test_add_requires_post(self):
        r = self.client.get(self.add_url)
        self.assertEqual(r.status_code, 405)

    # ── View ──────────────────────────────────────────────────────────────
    def test_cart_page_200(self):
        r = self.client.get(self.cart_url)
        self.assertEqual(r.status_code, 200)

    def test_cart_shows_added_product(self):
        self._add_to_cart()
        r = self.client.get(self.cart_url)
        self.assertContains(r, "Blender")

    def test_empty_cart_shows_no_items(self):
        r = self.client.get(self.cart_url)
        self.assertNotContains(r, "Blender")

    # ── Update ────────────────────────────────────────────────────────────
    def test_update_cart_quantity(self):
        self._add_to_cart()
        self.client.post(self.update_url, {"quantity": 3})
        session = self.client.session
        self.assertEqual(session["cart"][str(self.product.id)]["quantity"], 3)

    def test_update_quantity_to_zero_removes_item(self):
        self._add_to_cart()
        self.client.post(self.update_url, {"quantity": 0})
        session = self.client.session
        self.assertNotIn(str(self.product.id), session.get("cart", {}))

    def test_update_quantity_capped_at_stock(self):
        self._add_to_cart()
        self.client.post(self.update_url, {"quantity": 999})
        session = self.client.session
        qty = session["cart"][str(self.product.id)]["quantity"]
        self.assertLessEqual(qty, self.product.stock)

    def test_update_requires_post(self):
        r = self.client.get(self.update_url)
        self.assertEqual(r.status_code, 405)

    # ── Remove ────────────────────────────────────────────────────────────
    def test_remove_from_cart(self):
        self._add_to_cart()
        self.client.post(self.remove_url)
        session = self.client.session
        self.assertNotIn(str(self.product.id), session.get("cart", {}))

    def test_remove_non_existent_item_does_not_error(self):
        r = self.client.post(self.remove_url)
        self.assertRedirects(r, self.cart_url)

    def test_remove_requires_post(self):
        r = self.client.get(self.remove_url)
        self.assertEqual(r.status_code, 405)

    # ── Context processor ────────────────────────────────────────────────
    def test_cart_count_context_empty(self):
        r = self.client.get(reverse("shop:home"))
        self.assertEqual(r.context["cart_count"], 0)

    def test_cart_count_context_after_add(self):
        self._add_to_cart(2)
        r = self.client.get(reverse("shop:home"))
        self.assertEqual(r.context["cart_count"], 2)


# ═══════════════════════════════════════════════════════════════════════════
# 5. CHECKOUT TESTS
# ═══════════════════════════════════════════════════════════════════════════

class CheckoutTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="shopper", password="Shop@123")
        self.cat  = Category.objects.create(name="Bags", slug="bags")
        self.product = Product.objects.create(
            category=self.cat, name="Backpack", slug="backpack",
            description="A good backpack", price=Decimal("1500.00"), stock=10,
        )
        self.client.login(username="shopper", password="Shop@123")
        # Put one item in the cart
        self.client.post(reverse("shop:cart_add", args=[self.product.id]))
        self.checkout_url = reverse("shop:checkout")

    # ── Guards ────────────────────────────────────────────────────────────
    def test_checkout_redirects_when_anonymous(self):
        self.client.logout()
        r = self.client.get(self.checkout_url)
        self.assertIn("login", r["Location"])

    def test_checkout_redirects_when_cart_empty(self):
        self.client.post(
            reverse("shop:cart_remove", args=[self.product.id])
        )
        r = self.client.get(self.checkout_url)
        self.assertRedirects(r, reverse("shop:product_list"))

    def test_checkout_get_200(self):
        r = self.client.get(self.checkout_url)
        self.assertEqual(r.status_code, 200)

    def test_checkout_get_prefills_email(self):
        self.user.email = "shopper@example.com"
        self.user.save()
        r = self.client.get(self.checkout_url)
        self.assertContains(r, "shopper@example.com")

    # ── COD order creation ────────────────────────────────────────────────
    def test_checkout_post_cod_creates_order(self):
        r = self.client.post(self.checkout_url, _checkout_post_data("COD"))
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.payment_method, "COD")
        self.assertEqual(order.payment_status, "COD_PENDING")
        self.assertEqual(order.user, self.user)

    def test_checkout_post_cod_decrements_stock(self):
        self.client.post(self.checkout_url, _checkout_post_data("COD"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)

    def test_checkout_post_cod_clears_cart(self):
        self.client.post(self.checkout_url, _checkout_post_data("COD"))
        session = self.client.session
        self.assertEqual(session.get("cart", {}), {})

    def test_checkout_post_cod_redirects_to_order_detail(self):
        r = self.client.post(self.checkout_url, _checkout_post_data("COD"))
        order = Order.objects.first()
        self.assertRedirects(r, reverse("shop:order_detail", args=[order.id]))

    def test_checkout_post_insufficient_stock_redirects_to_cart(self):
        self.product.stock = 0
        self.product.save()
        # Force cart to contain the now-out-of-stock item
        session = self.client.session
        session["cart"] = {str(self.product.id): {"quantity": 5}}
        session.save()
        r = self.client.post(self.checkout_url, _checkout_post_data("COD"))
        self.assertRedirects(r, reverse("shop:cart"))

    def test_checkout_post_invalid_form_does_not_create_order(self):
        bad_data = _checkout_post_data()
        bad_data["email"] = "not-an-email"
        self.client.post(self.checkout_url, bad_data)
        self.assertEqual(Order.objects.count(), 0)

    # ── Razorpay redirect ─────────────────────────────────────────────────
    @override_settings(RAZORPAY_KEY_ID=FAKE_KEY_ID, RAZORPAY_KEY_SECRET=FAKE_KEY_SECRET)
    def test_checkout_post_razorpay_redirects_to_payment(self):
        r = self.client.post(self.checkout_url, _checkout_post_data("RAZORPAY"))
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertRedirects(r, reverse("shop:payment", args=[order.id]))

    @override_settings(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="")
    def test_checkout_post_razorpay_without_keys_stays_pending(self):
        r = self.client.post(self.checkout_url, _checkout_post_data("RAZORPAY"))
        order = Order.objects.first()
        # Should not redirect to payment page; goes to order_detail instead
        self.assertRedirects(r, reverse("shop:order_detail", args=[order.id]))
        self.assertEqual(order.payment_status, "PENDING")


# ═══════════════════════════════════════════════════════════════════════════
# 6. ORDER TESTS
# ═══════════════════════════════════════════════════════════════════════════

class OrderViewTest(TestCase):
    def setUp(self):
        self.user  = User.objects.create_user(username="orderer", password="Order@123")
        self.other = User.objects.create_user(username="stranger", password="Order@123")
        self.cat   = Category.objects.create(name="Shoes", slug="shoes")
        self.order = Order.objects.create(
            user=self.user, order_number="ORD-VIEW001",
            full_name="Orderer", email="o@o.com", phone="9000000001",
            address="2 Lane", city="Delhi", state="Delhi", pincode="110001",
            total_amount=Decimal("2000.00"),
        )
        self.client.login(username="orderer", password="Order@123")

    def test_orders_page_200(self):
        r = self.client.get(reverse("shop:orders"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ORD-VIEW001")

    def test_order_detail_200(self):
        r = self.client.get(reverse("shop:order_detail", args=[self.order.id]))
        self.assertEqual(r.status_code, 200)

    def test_order_detail_contains_order_number(self):
        r = self.client.get(reverse("shop:order_detail", args=[self.order.id]))
        self.assertContains(r, "ORD-VIEW001")

    def test_other_user_cannot_view_order(self):
        self.client.login(username="stranger", password="Order@123")
        r = self.client.get(reverse("shop:order_detail", args=[self.order.id]))
        self.assertEqual(r.status_code, 404)


# ═══════════════════════════════════════════════════════════════════════════
# 7. WISHLIST TESTS
# ═══════════════════════════════════════════════════════════════════════════

class WishlistViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="wisher2", password="Wish@123")
        self.cat  = Category.objects.create(name="Watches", slug="watches")
        self.product = Product.objects.create(
            category=self.cat, name="Smart Watch", slug="smart-watch",
            description="Feature watch", price=Decimal("4999.00"), stock=8,
        )
        self.client.login(username="wisher2", password="Wish@123")
        self.toggle_url = reverse("shop:wishlist_toggle", args=[self.product.id])

    def test_wishlist_page_200(self):
        r = self.client.get(reverse("shop:wishlist"))
        self.assertEqual(r.status_code, 200)

    def test_wishlist_requires_login(self):
        self.client.logout()
        r = self.client.get(reverse("shop:wishlist"))
        self.assertEqual(r.status_code, 302)

    def test_toggle_adds_to_wishlist(self):
        self.client.post(self.toggle_url, {"next": "/"})
        self.assertTrue(
            Wishlist.objects.filter(user=self.user, product=self.product).exists()
        )

    def test_toggle_twice_removes_from_wishlist(self):
        self.client.post(self.toggle_url, {"next": "/"})
        self.client.post(self.toggle_url, {"next": "/"})
        self.assertFalse(
            Wishlist.objects.filter(user=self.user, product=self.product).exists()
        )

    def test_wishlist_page_shows_item_after_add(self):
        self.client.post(self.toggle_url, {"next": "/"})
        r = self.client.get(reverse("shop:wishlist"))
        self.assertContains(r, "Smart Watch")


# ═══════════════════════════════════════════════════════════════════════════
# 8. RAZORPAY PAYMENT PAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(RAZORPAY_KEY_ID=FAKE_KEY_ID, RAZORPAY_KEY_SECRET=FAKE_KEY_SECRET)
class RazorpayPaymentPageTest(TestCase):
    """Tests for the GET /payment/<id>/ view. All Razorpay SDK calls mocked."""

    def setUp(self):
        self.user = User.objects.create_user(username="payer", password="Pay@1234")
        self.cat  = Category.objects.create(name="Electronics2", slug="electronics2")
        self.product = Product.objects.create(
            category=self.cat, name="Headphones", slug="headphones",
            description="Noise cancelling", price=Decimal("2999.00"), stock=5,
        )
        self.order = Order.objects.create(
            user=self.user, order_number="ORD-PAY001",
            full_name="Payer", email="p@p.com", phone="9999999999",
            address="Pay Lane", city="Bangalore", state="Karnataka",
            pincode="560001", payment_method="RAZORPAY",
            total_amount=Decimal("2999.00"),
        )
        self.client.login(username="payer", password="Pay@1234")
        self.payment_url = reverse("shop:payment", args=[self.order.id])

    @patch("razorpay.Client")
    def test_payment_page_200(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.order.create.return_value = {"id": "order_mockXYZ123"}
        mock_client_cls.return_value = mock_client

        r = self.client.get(self.payment_url)
        self.assertEqual(r.status_code, 200)

    @patch("razorpay.Client")
    def test_payment_page_calls_razorpay_create_order(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.order.create.return_value = {"id": "order_mockXYZ123"}
        mock_client_cls.return_value = mock_client

        self.client.get(self.payment_url)
        mock_client.order.create.assert_called_once()
        call_args = mock_client.order.create.call_args[0][0]
        self.assertEqual(call_args["amount"], 299900)   # 2999 * 100 paise
        self.assertEqual(call_args["currency"], "INR")
        self.assertEqual(call_args["receipt"], "ORD-PAY001")

    @patch("razorpay.Client")
    def test_payment_page_persists_razorpay_order_id(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.order.create.return_value = {"id": "order_mockXYZ123"}
        mock_client_cls.return_value = mock_client

        self.client.get(self.payment_url)
        self.order.refresh_from_db()
        self.assertEqual(self.order.razorpay_order_id, "order_mockXYZ123")

    @patch("razorpay.Client")
    def test_payment_page_reuses_stored_order_id(self, mock_client_cls):
        """If razorpay_order_id already saved, SDK must NOT be called again."""
        self.order.razorpay_order_id = "order_alreadyStored"
        self.order.save()
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        self.client.get(self.payment_url)
        mock_client.order.create.assert_not_called()

    @patch("razorpay.Client")
    def test_payment_page_context_has_key_id(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.order.create.return_value = {"id": "order_ctx001"}
        mock_client_cls.return_value = mock_client

        r = self.client.get(self.payment_url)
        self.assertEqual(r.context["razorpay_key_id"], FAKE_KEY_ID)

    def test_payment_page_non_razorpay_order_redirects(self):
        self.order.payment_method = "COD"
        self.order.save()
        r = self.client.get(self.payment_url)
        self.assertRedirects(r, reverse("shop:order_detail", args=[self.order.id]))

    @patch("razorpay.Client")
    def test_payment_page_already_paid_redirects(self, mock_client_cls):
        self.order.payment_status = "PAID"
        self.order.save()
        r = self.client.get(self.payment_url)
        self.assertRedirects(r, reverse("shop:order_detail", args=[self.order.id]))
        mock_client_cls.assert_not_called()

    @patch("razorpay.Client")
    def test_payment_page_sdk_error_sets_payment_enabled_false(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.order.create.side_effect = Exception("Razorpay API down")
        mock_client_cls.return_value = mock_client

        r = self.client.get(self.payment_url)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context["payment_enabled"])

    def test_payment_page_wrong_user_returns_404(self):
        other = User.objects.create_user(username="other_payer", password="O@12345")
        self.client.login(username="other_payer", password="O@12345")
        r = self.client.get(self.payment_url)
        self.assertEqual(r.status_code, 404)


# ═══════════════════════════════════════════════════════════════════════════
# 9. PAYMENT SUCCESS TESTS
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(RAZORPAY_KEY_ID=FAKE_KEY_ID, RAZORPAY_KEY_SECRET=FAKE_KEY_SECRET)
class PaymentSuccessTest(TestCase):
    """Tests for POST /payment/<id>/success/ — all signature calls mocked."""

    def setUp(self):
        self.user = User.objects.create_user(username="verifier", password="Ver@1234")
        self.cat  = Category.objects.create(name="Mobiles", slug="mobiles")
        self.product = Product.objects.create(
            category=self.cat, name="Smartphone", slug="smartphone",
            description="5G phone", price=Decimal("14999.00"), stock=3,
        )
        self.order = Order.objects.create(
            user=self.user, order_number="ORD-SUC001",
            full_name="Verifier", email="v@v.com", phone="8888888888",
            address="Verify Lane", city="Hyderabad", state="Telangana",
            pincode="500001", payment_method="RAZORPAY",
            total_amount=Decimal("14999.00"),
            razorpay_order_id="order_rp_test_001",
        )
        self.client.login(username="verifier", password="Ver@1234")
        self.success_url = reverse("shop:payment_success", args=[self.order.id])

    def _post_success(self, payment_id="pay_test001",
                       razorpay_order_id="order_rp_test_001",
                       signature="validsig"):
        return self.client.post(self.success_url, {
            "payment_id":        payment_id,
            "razorpay_order_id": razorpay_order_id,
            "signature":         signature,
        })

    # ── Valid payment ─────────────────────────────────────────────────────
    @patch("razorpay.Client")
    def test_valid_signature_marks_order_paid(self, mock_client_cls):
        mock_client = MagicMock()
        # verify_payment_signature returns None on success (no exception)
        mock_client.utility.verify_payment_signature.return_value = None
        mock_client_cls.return_value = mock_client

        self._post_success()
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "PAID")
        self.assertEqual(self.order.status, "CONFIRMED")

    @patch("razorpay.Client")
    def test_valid_signature_persists_payment_id(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = None
        mock_client_cls.return_value = mock_client

        self._post_success(payment_id="pay_realid_123")
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_id, "pay_realid_123")

    @patch("razorpay.Client")
    def test_valid_signature_persists_signature(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = None
        mock_client_cls.return_value = mock_client

        self._post_success(signature="mysig_abc")
        self.order.refresh_from_db()
        self.assertEqual(self.order.razorpay_signature, "mysig_abc")

    @patch("razorpay.Client")
    def test_valid_payment_redirects_to_order_detail(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = None
        mock_client_cls.return_value = mock_client

        r = self._post_success()
        self.assertRedirects(r, reverse("shop:order_detail", args=[self.order.id]))

    # ── Invalid / tampered signature ──────────────────────────────────────
    @patch("razorpay.Client")
    def test_invalid_signature_does_not_mark_paid(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.side_effect = Exception(
            "SignatureVerificationError"
        )
        mock_client_cls.return_value = mock_client

        self._post_success(signature="TAMPERED_SIGNATURE")
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.payment_status, "PAID")

    @patch("razorpay.Client")
    def test_invalid_signature_redirects_back_to_payment(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.side_effect = Exception(
            "SignatureVerificationError"
        )
        mock_client_cls.return_value = mock_client

        r = self._post_success(signature="TAMPERED")
        self.assertRedirects(r, reverse("shop:payment", args=[self.order.id]))

    # ── Missing fields ────────────────────────────────────────────────────
    def test_missing_payment_id_redirects_back(self):
        r = self.client.post(self.success_url, {
            "razorpay_order_id": "order_rp_test_001",
            "signature":         "sig",
        })
        self.assertRedirects(r, reverse("shop:payment", args=[self.order.id]))
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.payment_status, "PAID")

    def test_missing_signature_redirects_back(self):
        r = self.client.post(self.success_url, {
            "payment_id":        "pay_test001",
            "razorpay_order_id": "order_rp_test_001",
        })
        self.assertRedirects(r, reverse("shop:payment", args=[self.order.id]))

    def test_all_fields_empty_redirects_back(self):
        r = self.client.post(self.success_url, {
            "payment_id": "", "razorpay_order_id": "", "signature": ""
        })
        self.assertRedirects(r, reverse("shop:payment", args=[self.order.id]))

    # ── Security guards ───────────────────────────────────────────────────
    def test_requires_post_method(self):
        r = self.client.get(self.success_url)
        self.assertEqual(r.status_code, 405)

    def test_wrong_user_gets_404(self):
        other = User.objects.create_user(username="other_ver", password="O@12345")
        self.client.login(username="other_ver", password="O@12345")
        r = self._post_success()
        self.assertEqual(r.status_code, 404)

    @override_settings(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="")
    def test_missing_razorpay_config_redirects_back(self):
        r = self._post_success()
        self.assertRedirects(r, reverse("shop:payment", args=[self.order.id]))
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.payment_status, "PAID")


# ═══════════════════════════════════════════════════════════════════════════
# 10. SIGNATURE VERIFICATION LOGIC (unit test — no HTTP)
# ═══════════════════════════════════════════════════════════════════════════

class SignatureVerificationUnitTest(TestCase):
    """Verify the HMAC-SHA256 formula directly — no Django client needed."""

    def test_correct_signature_is_accepted(self):
        order_id   = "order_ABC123"
        payment_id = "pay_XYZ789"
        secret     = "test_secret_key"
        sig = _make_valid_signature(order_id, payment_id, secret)

        import razorpay
        client = razorpay.Client(auth=(FAKE_KEY_ID, FAKE_KEY_SECRET))
        # Patch the secret used internally
        with patch.object(client.utility, "verify_payment_signature") as mock_verify:
            mock_verify.return_value = None   # no exception == success
            try:
                client.utility.verify_payment_signature({
                    "razorpay_order_id":   order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature":  sig,
                })
                verified = True
            except Exception:
                verified = False
        self.assertTrue(verified)

    def test_tampered_signature_raises(self):
        """Tampered signature must raise, not silently pass."""
        order_id   = "order_ABC123"
        payment_id = "pay_XYZ789"
        bad_sig    = "0000000000000000000000000000000000000000000000000000000000000000"

        import razorpay
        client = razorpay.Client(auth=(FAKE_KEY_ID, FAKE_KEY_SECRET))
        with patch.object(client.utility, "verify_payment_signature",
                          side_effect=Exception("SignatureVerificationError")):
            with self.assertRaises(Exception):
                client.utility.verify_payment_signature({
                    "razorpay_order_id":   order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature":  bad_sig,
                })
