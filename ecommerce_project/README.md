# 🛒 ShopKart – Django E-Commerce Website

ShopKart is a full-stack e-commerce web application built using Django.
It provides a complete shopping experience including product browsing,
cart management, wishlist, user authentication, order management, and
Razorpay payment integration.

---

## 🚀 Features

### 👤 User Authentication
- User registration
- User login and logout
- User profile
- Secure authentication using Django

### 🛍️ Product Management
- Product listing
- Product details
- Product categories
- Product images
- Product search/filtering
- Product stock management

### 🛒 Shopping Cart
- Add products to cart
- Update product quantity
- Remove products from cart
- Cart total calculation
- Checkout functionality

### ❤️ Wishlist
- Add products to wishlist
- Remove products from wishlist
- View wishlist products

### 📦 Order Management
- Create orders
- Order history
- Order details
- Order status management
- Order item tracking

### 💳 Razorpay Payment Integration
- Razorpay payment gateway
- Secure online payments
- Test-mode payment support
- Payment verification
- Order creation after successful payment

### 🖥️ Admin Panel
- Django admin interface
- Product management
- Order management
- User management
- Database management

---

## 🛠️ Technologies Used

| Technology | Purpose |
|------------|---------|
| Python | Backend programming |
| Django | Web framework |
| HTML5 | Frontend structure |
| CSS3 | Styling |
| JavaScript | Frontend interactions |
| SQLite | Development database |
| Razorpay | Payment gateway |
| Git | Version control |
| GitHub | Source code hosting |

---

## 📁 Project Structure

```text
ShopKart/
│
├── ecommerce_project/
│   │
│   ├── manage.py
│   │
│   ├── ecommerce/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   │
│   ├── shop/
│   │   ├── migrations/
│   │   ├── templates/
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── forms.py
│   │   ├── models.py
│   │   ├── tests.py
│   │   ├── urls.py
│   │   └── views.py
│   │
│   ├── templates/
│   ├── static/
│   ├── media/
│   ├── .env.example
│   ├── .gitignore
│   └── requirements.txt
│
└── README.md