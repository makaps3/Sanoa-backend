"""
Celery tasks for inventory app
"""
import logging
from celery import shared_task

logger = logging.getLogger('sanoa.inventory')


@shared_task
def check_low_stock_alerts():
    """Periodic task to check for low stock and create alerts"""
    from .models import InventoryItem, StockAlert

    low_stock_items = InventoryItem.objects.filter(
        stock_status__in=['low_stock', 'out_of_stock']
    ).select_related('product', 'warehouse')

    alerts_created = 0
    for item in low_stock_items:
        # Don't create duplicate active alerts
        existing = StockAlert.objects.filter(
            inventory_item=item,
            status='active',
            alert_type='low_stock' if item.stock_status == 'low_stock' else 'out_of_stock',
        ).exists()

        if not existing:
            alert_type = 'out_of_stock' if item.quantity_available == 0 else 'low_stock'
            StockAlert.objects.create(
                inventory_item=item,
                alert_type=alert_type,
                message=f'{item.product.name} at {item.warehouse.name}: '
                        f'{item.quantity_available} units available '
                        f'(minimum: {item.minimum_stock_level})',
                current_stock_level=item.quantity_available,
                threshold_level=item.minimum_stock_level,
            )
            alerts_created += 1

    logger.info(f"Low stock check complete: {alerts_created} new alerts created")
    return alerts_created
