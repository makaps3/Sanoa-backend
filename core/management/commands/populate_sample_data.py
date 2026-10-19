from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import random
from datetime import timedelta

from accounts.models import CustomerProfile, APIToken
from business.models import IndividualVendorProfile, BusinessVendorProfile, VendorProfile
from products.models import Category, Brand, Product, ProductImage, ProductReview
from orders.models import Order, OrderItem
from subscriptions.models import Plan, Subscription
from tiers.models import BusinessTier, VendorTierSubscription

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate database with sample data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Starting sample data population...')

        # Create sample users
        self.create_sample_users()

        # Create categories and brands
        self.create_categories_and_brands()

        # Create products
        self.create_products()

        # Create orders
        self.create_orders()

        # Create subscriptions
        self.create_subscriptions()

        self.stdout.write(self.style.SUCCESS('Sample data population completed!'))


    def create_sample_users(self):
        self.stdout.write('Creating sample users...')

        # Create admin
        admin, created = User.objects.get_or_create(
            email='admin@sanoa.com',
            defaults={
                'username': 'admin',
                'first_name': 'Admin',
                'last_name': 'User',
                'user_type': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()

        # Create customers
        customers_data = [
            {
                'email': 'john.doe@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'phone_number': '+27123456789',
            },
            {
                'email': 'jane.smith@example.com',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'phone_number': '+27123456790',
            },
            {
                'email': 'bob.johnson@example.com',
                'first_name': 'Bob',
                'last_name': 'Johnson',
                'phone_number': '+27123456791',
            },
        ]

        for data in customers_data:
            user, created = User.objects.get_or_create(
                email=data['email'],
                defaults={
                    'username': data['email'].split('@')[0],
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'phone_number': data['phone_number'],
                    'user_type': 'customer',
                    'is_verified': True,
                }
            )
            if created:
                user.set_password('password123')
                user.save()

            # Create or ensure customer profile exists
            CustomerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'gender': 'M' if data['first_name'] in ['John', 'Bob'] else 'F',
                    'bio': f"Hi, I'm {data['first_name']} and I'm excited to shop on Sanoa!",
                    'latitude': -26.2041 + random.uniform(-0.1, 0.1),  # Johannesburg area
                    'longitude': 28.0473 + random.uniform(-0.1, 0.1),
                    'preferred_language': 'en',
                    'newsletter_subscription': True,
                    'sms_notifications': True,
                    'email_notifications': True,
                    'loyalty_points': random.randint(0, 500),
                }
            )

        # Create vendors
        vendors_data = [
            {
                'email': 'sarah.bakery@example.com',
                'first_name': 'Sarah',
                'last_name': 'Johnson',
                'phone_number': '+27123456792',
                'store_name': "Sarah's Bakery",
                'vendor_type': 'home_business',
            },
            {
                'email': 'freshco.grocers@example.com',
                'first_name': 'Mike',
                'last_name': 'Davis',
                'phone_number': '+27123456793',
                'business_name': 'FreshCo Grocers',
                'business_type': 'pty_ltd',
                'business_category': 'retail',
            },
            {
                'email': 'mzansi.grill@example.com',
                'first_name': 'Emma',
                'last_name': 'Wilson',
                'phone_number': '+27123456794',
                'business_name': 'Mzansi Grill House',
                'business_type': 'sole_proprietor',
                'business_category': 'restaurant',
            },
        ]

        for data in vendors_data:
            user, created = User.objects.get_or_create(
                email=data['email'],
                defaults={
                    'username': data['email'].split('@')[0],
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'phone_number': data['phone_number'],
                    'user_type': 'vendor',
                    'is_verified': True,
                }
            )
            if created:
                user.set_password('password123')
                user.save()

                if 'store_name' in data:  # Individual vendor
                    IndividualVendorProfile.objects.create(
                        user=user,
                        business_category=data.get('business_category', 'retail'),
                        vendor_type=data['vendor_type'],
                        store_name=data['store_name'],
                        store_description=f"Welcome to {data['store_name']}! We offer quality products with excellent service.",
                        id_number=f"{random.randint(100000, 999999)}{random.randint(100000, 999999)}",
                        trading_address='123 Main Street, Johannesburg, South Africa',
                        trading_city='Johannesburg',
                        trading_province='Gauteng',
                        trading_postal_code='2000',
                        latitude=-26.2041 + random.uniform(-0.1, 0.1),
                        longitude=28.0473 + random.uniform(-0.1, 0.1),
                        bank_name='Standard Bank',
                        bank_account_number='1234567890',
                        bank_account_holder=f"{data['first_name']} {data['last_name']}",
                        verification_status='verified',
                        store_active=True,
                        total_sales=Decimal('15000.00'),
                        total_orders=150,
                        average_rating=Decimal('4.5'),
                        total_reviews=45,
                    )
                else:  # Business vendor
                    BusinessVendorProfile.objects.create(
                        user=user,
                        business_category=data.get('business_category', 'retail'),
                        business_name=data['business_name'],
                        business_type=data['business_type'],
                        business_description=f"{data['business_name']} offers premium products with exceptional quality.",
                        cipc_registration_number=f"2023/{random.randint(100000, 999999)}/07",
                        owner_full_name=f"{data['first_name']} {data['last_name']}",
                        owner_id_number=f"{random.randint(100000, 999999)}{random.randint(100000, 999999)}",
                        business_street_address='456 Business Avenue',
                        business_city='Johannesburg',
                        business_province='Gauteng',
                        business_postal_code='2000',
                        business_country='South Africa',
                        latitude=-26.2041 + random.uniform(-0.1, 0.1),
                        longitude=28.0473 + random.uniform(-0.1, 0.1),
                        bank_name='First National Bank',
                        bank_account_number='0987654321',
                        bank_account_holder=data['business_name'],
                        verification_status='verified',
                        store_active=True,
                        total_sales=Decimal('50000.00'),
                        total_orders=500,
                        average_rating=Decimal('4.7'),
                        total_reviews=120,
                    )


    def create_categories_and_brands(self):
        self.stdout.write('Creating categories and brands...')

        # Map sample data category labels to seed_categories taxonomy slugs
        category_slug_map = {
            'Bread': 'bakery-bread-rolls',
            'Biscuits': 'bakery-rusks-biscuits',
            'Milk': 'dairy-eggs-milk-maas',
            'Rice': 'pantry-staples-rice-pasta-noodles',
            'Biltong': 'snacks-sweets-biltong-droewors',
            'Tea': 'beverages-tea-coffee',
            'Burgers': 'burgers',
            'Grills': 'grills-braai',
        }

        categories = {}
        for label, slug in category_slug_map.items():
            try:
                categories[label] = Category.objects.get(slug=slug)
            except Category.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"Category '{slug}' not found. Run seed_categories first."
                ))

        # Create brands
        brands_data = [
            {'name': 'Local Bakery', 'description': 'Fresh baked goods'},
            {'name': 'Boland Dairy', 'description': 'Farm-fresh Western Cape dairy'},
            {'name': 'Mzansi Pantry', 'description': 'Everyday South African pantry staples'},
            {'name': 'Karoo Biltong Co', 'description': 'Traditional air-dried biltong and droewors'},
            {'name': 'Rooibos Valley', 'description': 'Cederberg rooibos tea'},
        ]

        brands = {}
        for data in brands_data:
            brand, created = Brand.objects.get_or_create(
                name=data['name'],
                defaults={
                    'description': data['description'],
                    'is_active': True,
                }
            )
            brands[data['name']] = brand

        self.categories = categories
        self.brands = brands


    def create_products(self):
        self.stdout.write('Creating products...')

        products_data = [
            {
                'name': 'Fresh Sourdough Bread',
                'description': 'Artisanal sourdough bread baked fresh daily',
                'price': Decimal('45.00'),
                'category': 'Bread',
                'brand': 'Local Bakery',
                'vendor_email': 'sarah.bakery@example.com',
            },
            {
                'name': 'Chocolate Chip Cookies',
                'description': 'Freshly baked chocolate chip cookies',
                'price': Decimal('25.00'),
                'category': 'Biscuits',
                'brand': 'Local Bakery',
                'vendor_email': 'sarah.bakery@example.com',
            },
            {
                'name': 'Full Cream Fresh Milk 2L',
                'description': 'Fresh full cream milk from Boland dairy farms',
                'price': Decimal('32.99'),
                'category': 'Milk',
                'brand': 'Boland Dairy',
                'vendor_email': 'freshco.grocers@example.com',
            },
            {
                'name': 'Long Grain White Rice 2kg',
                'description': 'Parboiled long grain rice for everyday meals',
                'price': Decimal('44.99'),
                'category': 'Rice',
                'brand': 'Mzansi Pantry',
                'vendor_email': 'freshco.grocers@example.com',
            },
            {
                'name': 'Beef Biltong 250g',
                'description': 'Traditional air-dried beef biltong, sliced',
                'price': Decimal('89.99'),
                'category': 'Biltong',
                'brand': 'Karoo Biltong Co',
                'vendor_email': 'freshco.grocers@example.com',
            },
            {
                'name': 'Rooibos Tea 80 Bags',
                'description': 'Naturally caffeine-free Cederberg rooibos',
                'price': Decimal('54.99'),
                'category': 'Tea',
                'brand': 'Rooibos Valley',
                'vendor_email': 'freshco.grocers@example.com',
            },
            {
                'name': 'Mzansi Beef Burger',
                'description': 'Flame-grilled beef burger with chakalaka relish',
                'price': Decimal('79.00'),
                'category': 'Burgers',
                'brand': None,
                'vendor_email': 'mzansi.grill@example.com',
            },
            {
                'name': 'Shisa Nyama Platter',
                'description': 'Boerewors, lamb chops and chicken with pap and sauce',
                'price': Decimal('159.00'),
                'category': 'Grills',
                'brand': None,
                'vendor_email': 'mzansi.grill@example.com',
            },
        ]

        for data in products_data:
            vendor = VendorProfile.objects.filter(user__email=data['vendor_email']).first()
            category = self.categories.get(data['category'])
            if vendor is None or category is None:
                self.stdout.write(self.style.WARNING(
                    f"Skipping {data['name']}: vendor or category missing."
                ))
                continue
            brand = self.brands.get(data['brand']) if data['brand'] else None

            product, created = Product.objects.get_or_create(
                name=data['name'],
                vendor=vendor,
                defaults={
                    'description': data['description'],
                    'short_description': data['description'][:100],
                    'category': category,
                    'brand': brand,
                    'price': data['price'],
                    'status': 'active',
                    'is_featured': random.choice([True, False]),
                    'requires_shipping': data['category'] not in ('Burgers', 'Grills'),
                    'weight': Decimal(str(random.uniform(0.1, 5.0))),
                    'length': Decimal(str(random.uniform(10, 50))),
                    'width': Decimal(str(random.uniform(5, 30))),
                    'height': Decimal(str(random.uniform(1, 20))),
                    'specifications': {
                        'Origin': 'South Africa'
                    },
                    'views_count': random.randint(10, 1000),
                    'sales_count': random.randint(0, 100),
                }
            )

            if created:
                # Create some reviews
                customers = User.objects.filter(user_type='customer')
                for _ in range(random.randint(0, 5)):
                    customer = random.choice(customers)
                    ProductReview.objects.get_or_create(
                        product=product,
                        user=customer,
                        defaults={
                            'rating': random.randint(3, 5),
                            'title': f"Great {data['name']}!",
                            'comment': f"I love this {data['name'].lower()}! Highly recommended.",
                            'is_approved': True,
                        }
                    )


    def create_orders(self):
        self.stdout.write('Creating orders...')

        customers = User.objects.filter(user_type='customer')
        products = Product.objects.all()

        for customer in customers:
            # Create 2-5 orders per customer
            for _ in range(random.randint(2, 5)):
                # Select random products from different vendors
                order_products = random.sample(list(products), random.randint(1, 3))

                # Calculate totals
                subtotal = sum(product.price for product in order_products)
                shipping_cost = Decimal('100.00') if subtotal < Decimal('500.00') else Decimal('0.00')
                tax_amount = subtotal * Decimal('0.15')  # 15% VAT
                total_amount = subtotal + shipping_cost + tax_amount

                order = Order.objects.create(
                    user=customer,
                    status=random.choice(['pending', 'processing', 'shipped', 'delivered']),
                    payment_status='paid',
                    subtotal=subtotal,
                    tax_amount=tax_amount,
                    shipping_cost=shipping_cost,
                    total_amount=total_amount,
                    customer_email=customer.email,
                    customer_phone=customer.phone_number,
                    billing_full_name=f"{customer.first_name} {customer.last_name}",
                    billing_street_address='123 Customer Street',
                    billing_city='Johannesburg',
                    billing_state_province='Gauteng',
                    billing_postal_code='2000',
                    billing_country='South Africa',
                    shipping_full_name=f"{customer.first_name} {customer.last_name}",
                    shipping_street_address='123 Customer Street',
                    shipping_city='Johannesburg',
                    shipping_state_province='Gauteng',
                    shipping_postal_code='2000',
                    shipping_country='South Africa',
                    created_at=timezone.now() - timedelta(days=random.randint(1, 30)),
                )

                # Create order items
                for product in order_products:
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=random.randint(1, 3),
                        vendor=product.vendor.user,
                        vendor_profile=product.vendor,
                    )

                # Update product sales count
                for product in order_products:
                    product.sales_count += 1
                    product.save()


    def create_subscriptions(self):
        self.stdout.write('Creating subscriptions and tiers...')

        # Create business tiers
        tiers_data = [
            {
                'name': 'Free',
                'price': Decimal('0.00'),
                'tier_level': 0,
                'max_products': 10,
                'commission_rate': Decimal('15.00'),
                'features': ['Basic store', 'Limited products'],
            },
            {
                'name': 'Growth',
                'price': Decimal('299.00'),
                'tier_level': 1,
                'max_products': 100,
                'commission_rate': Decimal('12.00'),
                'features': ['Advanced analytics', 'Priority support', 'More products'],
            },
            {
                'name': 'Premium',
                'price': Decimal('999.00'),
                'tier_level': 2,
                'max_products': 0,  # Unlimited
                'commission_rate': Decimal('8.00'),
                'features': ['Unlimited products', 'Negotiation tools', 'Featured listings', 'VIP support'],
            },
        ]

        for data in tiers_data:
            tier, created = BusinessTier.objects.get_or_create(
                name=data['name'],
                defaults={
                    'slug': data['name'].lower(),
                    'description': f"{data['name']} tier for businesses",
                    'price': data['price'],
                    'tier_level': data['tier_level'],
                    'max_products': data['max_products'],
                    'commission_rate': data['commission_rate'],
                    'features': data['features'],
                    'is_active': True,
                }
            )

        # Assign tiers to vendors
        vendors = User.objects.filter(user_type='vendor')
        tiers = BusinessTier.objects.all()

        for vendor in vendors:
            tier = random.choice(tiers)
            VendorTierSubscription.objects.get_or_create(
                vendor=vendor,
                defaults={
                    'tier': tier,
                    'status': 'active',
                    'current_period_start': timezone.now(),
                    'current_period_end': timezone.now() + timedelta(days=30),
                }
            )

        # Create subscription plans
        plans_data = [
            {
                'name': 'Basic Credit',
                'price': Decimal('99.00'),
                'credit_limit': Decimal('1000.00'),
                'interest_rate': Decimal('2.5'),
                'max_items_on_credit': 3,
                'features': ['R1000 credit limit', 'Basic support'],
            },
            {
                'name': 'Premium Credit',
                'price': Decimal('199.00'),
                'credit_limit': Decimal('5000.00'),
                'interest_rate': Decimal('1.8'),
                'max_items_on_credit': 10,
                'features': ['R5000 credit limit', 'Priority support', 'Lower interest'],
            },
            {
                'name': 'VIP Credit',
                'price': Decimal('399.00'),
                'credit_limit': Decimal('15000.00'),
                'interest_rate': Decimal('1.2'),
                'max_items_on_credit': 0,  # Unlimited
                'features': ['R15000 credit limit', 'VIP support', 'Lowest interest', 'Exclusive deals'],
            },
        ]

        for data in plans_data:
            plan, created = Plan.objects.get_or_create(
                name=data['name'],
                defaults={
                    'slug': data['name'].lower().replace(' ', '-'),
                    'description': f"{data['name']} subscription plan",
                    'price': data['price'],
                    'credit_limit': data['credit_limit'],
                    'interest_rate': data['interest_rate'],
                    'max_items_on_credit': data['max_items_on_credit'],
                    'features': data['features'],
                    'is_active': True,
                }
            )

        # Create subscriptions for some customers
        customers = User.objects.filter(user_type='customer')
        plans = Plan.objects.all()

        for customer in random.sample(list(customers), 2):  # Subscribe 2 customers
            plan = random.choice(plans)
            Subscription.objects.get_or_create(
                user=customer,
                defaults={
                    'plan': plan,
                    'status': 'active',
                    'current_period_start': timezone.now(),
                    'current_period_end': timezone.now() + timedelta(days=30),
                }
            )