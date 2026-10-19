from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

User = get_user_model()


class Warehouse(models.Model):
    """Warehouse/fulfillment center model"""
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    
    # Address
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    
    # Contact info
    phone_number = models.CharField(max_length=17, blank=True)
    email = models.EmailField(blank=True)

    # Vendor that owns this warehouse
    vendor = models.ForeignKey(
        'business.VendorProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='warehouses',
    )

    # User who created this warehouse (set from JWT on creation)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_warehouses',
    )

    # Settings
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Warehouse'
        verbose_name_plural = 'Warehouses'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def save(self, *args, **kwargs):
        if self.is_default:
            # Ensure only one default warehouse
            Warehouse.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class InventoryItem(models.Model):
    """Inventory tracking for products"""
    
    STOCK_STATUS_CHOICES = [
        ('in_stock', 'In Stock'),
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('backordered', 'Backordered'),
        ('discontinued', 'Discontinued'),
    ]
    
    # Product relationship
    product = models.ForeignKey(
        'products.Product', 
        on_delete=models.CASCADE, 
        related_name='inventory_items'
    )
    product_variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='inventory_items'
    )
    
    # Location
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='inventory_items')
    location_code = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Specific location within warehouse (aisle, shelf, bin, etc.)"
    )
    
    # Stock levels
    quantity_on_hand = models.PositiveIntegerField(default=0)
    quantity_reserved = models.PositiveIntegerField(default=0)  # Reserved for orders
    quantity_available = models.PositiveIntegerField(default=0)  # Available for sale
    
    # Stock management settings
    minimum_stock_level = models.PositiveIntegerField(
        default=10,
        help_text="Minimum stock level before triggering low stock alerts"
    )
    maximum_stock_level = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum stock level for this item"
    )
    reorder_point = models.PositiveIntegerField(
        default=20,
        help_text="Stock level at which to reorder"
    )
    reorder_quantity = models.PositiveIntegerField(
        default=50,
        help_text="Quantity to order when restocking"
    )
    
    # Status
    stock_status = models.CharField(max_length=20, choices=STOCK_STATUS_CHOICES, default='in_stock')
    
    # Costing
    unit_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Cost per unit for inventory valuation"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Inventory Item'
        verbose_name_plural = 'Inventory Items'
        unique_together = ['product', 'product_variant', 'warehouse']
        indexes = [
            models.Index(fields=['product', 'warehouse']),
            models.Index(fields=['stock_status']),
            models.Index(fields=['quantity_available']),
        ]
    
    def __str__(self):
        variant_text = f" ({self.product_variant.name})" if self.product_variant else ""
        return f"{self.product.name}{variant_text} - {self.warehouse.name}"
    
    def save(self, *args, **kwargs):
        # Calculate available quantity
        self.quantity_available = max(0, self.quantity_on_hand - self.quantity_reserved)
        
        # Update stock status based on available quantity
        if self.quantity_available == 0:
            self.stock_status = 'out_of_stock'
        elif self.quantity_available <= self.minimum_stock_level:
            self.stock_status = 'low_stock'
        else:
            self.stock_status = 'in_stock'
        
        super().save(*args, **kwargs)
    
    @property
    def is_low_stock(self):
        return self.quantity_available <= self.minimum_stock_level
    
    @property
    def needs_reorder(self):
        return self.quantity_available <= self.reorder_point
    
    @property
    def inventory_value(self):
        """Total value of inventory at cost"""
        if self.unit_cost:
            return self.quantity_on_hand * self.unit_cost
        return Decimal('0.00')


class StockMovement(models.Model):
    """Track all stock movements/transactions"""
    
    MOVEMENT_TYPE_CHOICES = [
        ('purchase', 'Purchase/Received'),
        ('sale', 'Sale'),
        ('return', 'Return'),
        ('adjustment', 'Adjustment'),
        ('transfer', 'Transfer'),
        ('damage', 'Damage'),
        ('theft', 'Theft'),
        ('expired', 'Expired'),
        ('reserved', 'Reserved'),
        ('unreserved', 'Unreserved'),
    ]
    
    # Basic info
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory_item = models.ForeignKey(
        InventoryItem, 
        on_delete=models.CASCADE, 
        related_name='stock_movements'
    )
    
    # Movement details
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
    quantity = models.IntegerField(help_text="Positive for inbound, negative for outbound")
    
    # Related objects
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements'
    )
    purchase_order = models.ForeignKey(
        'PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements'
    )
    
    # User who performed the movement
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements'
    )
    
    # Additional details
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost per unit at time of movement"
    )
    
    # Quantities before and after movement (for audit trail)
    quantity_before = models.PositiveIntegerField()
    quantity_after = models.PositiveIntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['inventory_item', 'movement_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['order']),
        ]
    
    def __str__(self):
        return f"{self.movement_type} - {self.quantity} units - {self.inventory_item}"
    
    @property
    def total_cost(self):
        """Total cost of this movement"""
        if self.unit_cost:
            return abs(self.quantity) * self.unit_cost
        return Decimal('0.00')


class PurchaseOrder(models.Model):
    """Purchase orders for restocking inventory"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('confirmed', 'Confirmed'),
        ('partially_received', 'Partially Received'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Basic info
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po_number = models.CharField(max_length=50, unique=True, blank=True)
    
    # Supplier info
    supplier = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='purchase_orders',
    )

    # Destination
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='purchase_orders')
    
    # Status and dates
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    order_date = models.DateTimeField(auto_now_add=True)
    expected_delivery_date = models.DateTimeField(null=True, blank=True)
    actual_delivery_date = models.DateTimeField(null=True, blank=True)
    
    # Financial
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Additional info
    notes = models.TextField(blank=True)
    terms_and_conditions = models.TextField(blank=True)
    
    # Created by
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_purchase_orders'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"PO {self.po_number} - {self.supplier}"
    
    def save(self, *args, **kwargs):
        if not self.po_number:
            # Generate PO number
            import datetime
            today = datetime.date.today()
            prefix = f"PO-{today.strftime('%Y%m%d')}-"
            
            # Find the last PO number for today
            last_po = PurchaseOrder.objects.filter(
                po_number__startswith=prefix
            ).order_by('po_number').last()
            
            if last_po:
                last_num = int(last_po.po_number.split('-')[-1])
                new_num = f"{last_num + 1:04d}"
            else:
                new_num = "0001"
            
            self.po_number = f"{prefix}{new_num}"
        
        super().save(*args, **kwargs)
    
    def calculate_totals(self):
        """Calculate order totals based on line items"""
        self.subtotal = sum(item.total_cost for item in self.line_items.all())
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_cost
        self.save()


class PurchaseOrderLineItem(models.Model):
    """Line items in purchase orders"""
    
    purchase_order = models.ForeignKey(
        PurchaseOrder, 
        on_delete=models.CASCADE, 
        related_name='line_items'
    )
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    product_variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    # Quantities
    quantity_ordered = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    quantity_received = models.PositiveIntegerField(default=0)
    
    # Pricing
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Additional info
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Purchase Order Line Item'
        verbose_name_plural = 'Purchase Order Line Items'
    
    def __str__(self):
        variant_text = f" ({self.product_variant.name})" if self.product_variant else ""
        return f"{self.product.name}{variant_text} - {self.quantity_ordered} units"
    
    def save(self, *args, **kwargs):
        self.total_cost = self.quantity_ordered * self.unit_cost
        super().save(*args, **kwargs)
    
    @property
    def is_fully_received(self):
        return self.quantity_received >= self.quantity_ordered
    
    @property
    def quantity_pending(self):
        return max(0, self.quantity_ordered - self.quantity_received)


class StockAlert(models.Model):
    """Alerts for low stock, out of stock, etc."""
    
    ALERT_TYPE_CHOICES = [
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('reorder_point', 'Reorder Point Reached'),
        ('overstock', 'Overstock'),
        ('expired', 'Expired Items'),
        ('damage', 'Damaged Items'),
    ]
    
    ALERT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=ALERT_STATUS_CHOICES, default='active')
    
    # Alert details
    message = models.TextField()
    current_stock_level = models.PositiveIntegerField()
    threshold_level = models.PositiveIntegerField(null=True, blank=True)
    
    # Actions taken
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Stock Alert'
        verbose_name_plural = 'Stock Alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['alert_type', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.alert_type} - {self.inventory_item} - {self.status}"
    
    def acknowledge(self, user):
        """Acknowledge the alert"""
        from django.utils import timezone
        self.status = 'acknowledged'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()
    
    def resolve(self, user, notes=''):
        """Resolve the alert"""
        from django.utils import timezone
        self.status = 'resolved'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.resolution_notes = notes
        self.save()
