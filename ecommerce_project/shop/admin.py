from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Product, Order, OrderItem, Wishlist


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("image_preview", "name", "category", "price", "stock", "is_active", "created_at")
    list_filter = ("is_active", "category")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("price", "stock", "is_active")
    readonly_fields = ("image_preview_large",)

    fieldsets = (
        ("Product Info", {
            "fields": ("name", "slug", "category", "description", "price", "stock", "is_active")
        }),
        ("Product Image", {
            "fields": ("image", "image_preview_large"),
            "description": "Upload a real product image (JPG/PNG/WEBP). "
                           "Recommended size: 800×800px. "
                           "File will be saved to media/products/."
        }),
    )

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:50px;width:50px;object-fit:contain;'
                'background:#f1f5ff;border-radius:6px;padding:2px;" />',
                obj.image.url
            )
        return "—"

    @admin.display(description="Current Image")
    def image_preview_large(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:220px;max-width:300px;object-fit:contain;'
                'background:#f1f5ff;border-radius:10px;padding:8px;border:1px solid #e5e7eb;" />',
                obj.image.url
            )
        return "No image uploaded yet."


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name", "price", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number", "user", "total_amount",
        "payment_method", "payment_status", "status", "created_at"
    )
    list_filter = ("status", "payment_method", "payment_status")
    search_fields = ("order_number", "user__username", "email", "phone", "payment_id")
    readonly_fields = (
        "order_number", "total_amount", "created_at", "updated_at",
        "razorpay_order_id", "payment_id", "razorpay_signature",
    )
    list_editable = ("status",)
    inlines = [OrderItemInline]

    fieldsets = (
        ("Order Info", {
            "fields": (
                "order_number", "user", "status",
                "total_amount", "created_at", "updated_at",
            )
        }),
        ("Delivery", {
            "fields": ("full_name", "email", "phone", "address", "city", "state", "pincode")
        }),
        ("Payment", {
            "fields": (
                "payment_method", "payment_status",
                "razorpay_order_id", "payment_id", "razorpay_signature",
            ),
            "description": (
                "razorpay_order_id and payment_id are auto-filled after "
                "a successful Razorpay payment. All three fields are read-only."
            ),
        }),
    )


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")
    search_fields = ("user__username", "product__name")
