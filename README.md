<<<<<<< HEAD
# Sanoa E-commerce Backend

A comprehensive Django-based e-commerce backend API built with Django REST Framework.

## Features

### 🔐 Authentication & User Management
- Custom user model with customer and vendor profiles
- JWT-based authentication
- Role-based access (Customer, Vendor, Admin)
- User profiles with preferences and loyalty points
- Address management

### 🛍️ Product Management
- Hierarchical product categories
- Brand management
- Product variants (size, color, etc.)
- Product attributes and specifications
- Product images with automatic resizing
- Product reviews and ratings
- Wishlist functionality
- SEO-friendly slugs

### 📦 Order Management
- Shopping cart functionality
- Complete order lifecycle management
- Order status tracking with history
- Multi-vendor order support
- Coupon and discount system
- Order notes and internal comments

### 💳 Payment Processing
- Multiple payment method support
- Payment transaction tracking
- Refund management
- Payment webhooks handling
- Detailed payment logs
- Processing fee calculations

### 📊 Inventory Management
- Multi-warehouse support
- Stock level tracking
- Low stock alerts
- Stock movement audit trail
- Purchase order management
- Automatic stock status updates

## Tech Stack

- **Django 5.2.6** - Python web framework
- **Django REST Framework** - API development
- **Django Simple JWT** - JWT authentication
- **Pillow** - Image processing
- **Django CORS Headers** - Cross-origin resource sharing
- **Django Filter** - API filtering
- **Python Decouple** - Environment configuration

## Installation

### Prerequisites
- Python 3.8+
- pip
- Virtual environment (recommended)

### Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd sanoa/backend
```

2. **Create virtual environment**
```bash
python -m venv venv
```

3. **Activate virtual environment**
```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

4. **Install dependencies**
```bash
pip install -r requirements.txt
```

5. **Environment Configuration**
Create a `.env` file in the project root:
```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

6. **Run migrations**
```bash
python manage.py migrate
```

7. **Create superuser**
```bash
python manage.py createsuperuser
```

8. **Run development server**
```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000/api/`
Admin interface at `http://localhost:8000/admin/`

## API Endpoints

### Authentication
- `POST /api/auth/token/` - Obtain JWT token
- `POST /api/auth/token/refresh/` - Refresh JWT token
- `POST /api/auth/token/verify/` - Verify JWT token

### User Management
- `/api/accounts/` - User and profile management endpoints

### Products
- `/api/products/` - Product, category, and brand management

### Orders
- `/api/orders/` - Order and cart management

### Payments
- `/api/payments/` - Payment processing endpoints

### Inventory
- `/api/inventory/` - Inventory and warehouse management

## Database Models

### Accounts App
- **User** - Extended Django user model
- **CustomerProfile** - Customer-specific profile data
- **VendorProfile** - Vendor/seller profile with business info
- **Address** - User addresses for billing and shipping

### Products App
- **Category** - Hierarchical product categories
- **Brand** - Product brands
- **Product** - Main product model
- **ProductVariant** - Product variations (size, color, etc.)
- **ProductImage** - Product images
- **ProductAttribute** - Product specifications
- **ProductReview** - Customer reviews and ratings
- **Wishlist** - User wishlist items

### Orders App
- **ShoppingCart** - User shopping cart
- **CartItem** - Items in shopping cart
- **Order** - Customer orders
- **OrderItem** - Individual order line items
- **OrderStatusHistory** - Order status change tracking
- **Coupon** - Discount codes and coupons

### Payments App
- **PaymentMethod** - Available payment methods
- **CustomerPaymentMethod** - Saved customer payment methods
- **Payment** - Payment transactions
- **Refund** - Payment refunds
- **PaymentLog** - Payment activity logs
- **PaymentWebhook** - Webhook data from payment providers

### Inventory App
- **Warehouse** - Warehouse/fulfillment centers
- **InventoryItem** - Stock tracking per product/warehouse
- **StockMovement** - Stock movement audit trail
- **PurchaseOrder** - Purchase orders for restocking
- **PurchaseOrderLineItem** - Purchase order line items
- **StockAlert** - Low stock and other inventory alerts

## Admin Interface

The Django admin interface provides a complete management system for:

- User management and profiles
- Product catalog management
- Order processing and tracking
- Payment monitoring
- Inventory management
- Stock level monitoring

Access at `http://localhost:8000/admin/` with your superuser credentials.

## Development

### Adding New Features
1. Create models in the appropriate app
2. Run migrations: `python manage.py makemigrations && python manage.py migrate`
3. Register models in admin.py
4. Create serializers for API endpoints
5. Create ViewSets for API functionality
6. Add URL patterns

### Code Organization
```
sanoa/
├── accounts/          # User management
├── products/          # Product catalog
├── orders/           # Order processing
├── payments/         # Payment handling
├── inventory/        # Stock management
├── sanoa/            # Project settings
├── media/            # Uploaded files
├── staticfiles/      # Static files
└── requirements.txt  # Dependencies
```

## Security Features

- JWT-based authentication
- Role-based access control
- CORS configuration
- Secure password validation
- Input validation and sanitization
- Protection against common vulnerabilities

## Performance Considerations

- Database query optimization with select_related()
- Image optimization and resizing
- Pagination for large datasets
- Efficient admin interfaces
- Proper database indexing

## Future Enhancements

- API documentation with Swagger/OpenAPI
- Comprehensive test suite
- Docker containerization
- Redis caching
- Celery for background tasks
- Advanced search functionality
- Analytics and reporting
- Multi-language support

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests for new functionality
5. Submit a pull request

## License

This project is proprietary software. All rights reserved.

## Support

For support and questions, please contact the development team.
=======
# Sanoa-backend
Backend application for sanoa mobile and web app
>>>>>>> a59693adc1f46eda07b21eaa9448b2753ced248c
