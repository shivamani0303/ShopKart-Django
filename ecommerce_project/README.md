# ShopKart - Django E-Commerce Platform

A complete internship-ready e-commerce shopping platform built with Django, MySQL, Bootstrap 5 and JavaScript.

## Implemented features

- User registration, login, logout and profile
- Product catalog with categories
- Product search and category filtering
- Product detail page
- Session-based shopping cart
- Add, update and remove cart items
- Cart total calculation
- Checkout with shipping address
- Order creation and order history
- Order detail and status tracking
- Wishlist
- Django admin for products, categories, orders and users
- Razorpay payment integration structure using test mode
- Responsive Bootstrap UI
- Seed command for demo data
- SQLite fallback for easy local testing
- Production-oriented environment variables

## 1. Create virtual environment

Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

Linux/macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

## 2. Install packages

```bash
pip install -r requirements.txt
```

If `mysqlclient` fails to install on Windows, install MySQL Server/Connector and the required C++ build tools, or temporarily use SQLite by setting `USE_SQLITE=True`.

## 3. Configure environment

Copy `.env.example` to `.env`.

For MySQL:
```env
USE_SQLITE=False
DB_NAME=ecommerce_db
DB_USER=ecommerce_user
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

For quick testing without MySQL:
```env
USE_SQLITE=True
```

## 4. MySQL setup

Open MySQL and run:

```sql
CREATE DATABASE ecommerce_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'ecommerce_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON ecommerce_db.* TO 'ecommerce_user'@'localhost';
FLUSH PRIVILEGES;
```

## 5. Migrate and create admin

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

## 6. Add demo products

```bash
python manage.py seed_data
```

## 7. Run

```bash
python manage.py runserver
```

Open:
- Store: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

## Razorpay

The project includes Razorpay order creation and verification. For development, use Razorpay test credentials in `.env`.

```env
RAZORPAY_KEY_ID=your_test_key
RAZORPAY_KEY_SECRET=your_test_secret
```

Never commit real payment keys to GitHub.

## Main project structure

```text
ecommerce_project/
├── ecommerce/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── shop/
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── urls.py
│   ├── views.py
│   ├── context_processors.py
│   ├── migrations/
│   ├── management/commands/seed_data.py
│   └── templates/shop/
├── templates/
│   └── registration/
├── static/
│   ├── css/style.css
│   └── js/main.js
├── media/
├── manage.py
└── requirements.txt
```

## Internship feature mapping

| Requirement | Implementation |
|---|---|
| User Authentication | Django auth |
| Product Catalog | Category + Product models |
| Shopping Cart | Session-based cart |
| Checkout | Shipping + order creation |
| Order Management | Order history/status |
| Admin Dashboard | Django admin |
| Payment Integration | Razorpay test-mode flow |
| Wishlist | Wishlist model |



## Recommended demo sequence

1. Register a user.
2. Browse Products and test search/category filters.
3. Add products to Cart and change quantities.
4. Add/remove a product from Wishlist.
5. Login and complete Checkout with COD.
6. Open My Orders and inspect the order status.
7. Login to `/admin/` as the superuser and change product stock/order status.
8. For Razorpay, configure test keys and test the payment flow.

## Important production notes

- Use HTTPS in production.
- Keep `SECRET_KEY` and payment credentials in environment variables.
- Use Razorpay signature verification (implemented in this project).
- Add a proper payment webhook before treating asynchronous gateway events as final.
- Configure `ALLOWED_HOSTS`, secure cookies, CSRF trusted origins and a production database before deployment.


### Demo catalog
The `seed_data` command creates 50 products with local SVG product artwork across Electronics, Fashion, Home, Beauty and Sports.
