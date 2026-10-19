"""
Views for inventory app
"""
from rest_framework import viewsets, permissions, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Warehouse, InventoryItem, StockMovement, PurchaseOrder, StockAlert
from .serializers import (
    WarehouseSerializer, InventoryItemSerializer,
    StockMovementSerializer, PurchaseOrderSerializer,
    VendorPurchaseOrderCreateSerializer, StockAlertSerializer,
)
from core.permissions import IsAdminUser, IsVendorOrAdmin
from core.pagination import StandardPagination


def _resolve_vendor(request, vendor_uuid):
    """
    Look up VendorProfile by UUID and verify ownership.
    Returns (vendor_profile, None) on success or (None, error Response) on failure.
    """
    from business.models import VendorProfile
    try:
        vp = VendorProfile.objects.get(id=vendor_uuid)
    except VendorProfile.DoesNotExist:
        return None, Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not request.user.is_staff:
        user_vp = getattr(request.user, 'vendor_profile', None)
        if user_vp != vp:
            return None, Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
    return vp, None


def _get_vendor_public(vendor_uuid):
    """
    Look up VendorProfile by UUID only — no auth check.
    Used by public vendor-scoped endpoints that require no JWT.
    Returns (vendor_profile, None) on success or (None, error Response) on failure.
    """
    from business.models import VendorProfile
    try:
        return VendorProfile.objects.get(id=vendor_uuid), None
    except VendorProfile.DoesNotExist:
        return None, Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)


# ─── Admin-only viewsets ────────────────────────────────────────────────────


class WarehouseViewSet(viewsets.ModelViewSet):
    """Admin: manage platform warehouses."""
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    search_fields = ['name', 'code', 'city']


class InventoryItemViewSet(viewsets.ModelViewSet):
    """Admin: view and manage all inventory items across all vendors."""
    serializer_class = InventoryItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    search_fields = ['product__name', 'location_code']
    filterset_fields = ['warehouse', 'stock_status']
    ordering = ['product__name']

    def get_queryset(self):
        return InventoryItem.objects.select_related(
            'product', 'product_variant', 'warehouse'
        )

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        items = self.get_queryset().filter(stock_status='low_stock')
        return Response(self.get_serializer(items, many=True).data)

    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        items = self.get_queryset().filter(stock_status='out_of_stock')
        return Response(self.get_serializer(items, many=True).data)


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin: read-only audit trail of all stock movements."""
    serializer_class = StockMovementSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    ordering = ['-created_at']
    filterset_fields = ['movement_type', 'inventory_item']

    def get_queryset(self):
        return StockMovement.objects.select_related(
            'inventory_item__product', 'performed_by'
        )


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """Admin: manage all purchase orders across all vendors."""
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    search_fields = ['po_number', 'notes']
    filterset_fields = ['status', 'warehouse']
    ordering = ['-created_at']

    def get_queryset(self):
        return PurchaseOrder.objects.select_related(
            'supplier', 'warehouse', 'created_by'
        ).prefetch_related('line_items')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class StockAlertViewSet(viewsets.ModelViewSet):
    """Admin: view and action on all stock alerts."""
    serializer_class = StockAlertSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    filterset_fields = ['alert_type', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        return StockAlert.objects.select_related(
            'inventory_item__product', 'inventory_item__warehouse'
        )

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.acknowledge(request.user)
        return Response(StockAlertSerializer(alert).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        alert = self.get_object()
        notes = request.data.get('resolution_notes', '')
        alert.resolve(request.user, notes=notes)
        return Response(StockAlertSerializer(alert).data)


# ─── Vendor-scoped views ─────────────────────────────────────────────────────


class VendorInventoryItemsView(generics.ListCreateAPIView):
    """
    GET  /api/inventory/vendor/<vendor_uuid>/items/ — authenticated owner or administrator only.
    POST /api/inventory/vendor/<vendor_uuid>/items/ — JWT required; vendor must own vendor_uuid.
         Product in the request body must belong to this vendor.
    Supports ?stock_status=low_stock|out_of_stock|in_stock for GET filtering.
    """
    serializer_class = InventoryItemSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsVendorOrAdmin()]

    def get_queryset(self):
        vp, err = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if err:
            return InventoryItem.objects.none()
        qs = InventoryItem.objects.filter(
            product__vendor=vp
        ).select_related('product', 'product_variant', 'warehouse')
        stock_status = self.request.query_params.get('stock_status')
        if stock_status:
            qs = qs.filter(stock_status=stock_status)
        return qs

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        vp, err = _resolve_vendor(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        from products.models import Product
        product_id = request.data.get('product')
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        if product.vendor != vp:
            return Response(
                {'error': 'Product does not belong to this vendor.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)


class VendorStockMovementsView(generics.ListAPIView):
    """
    GET /api/inventory/vendor/<vendor_uuid>/movements/
    Authenticated owner or administrator only. Returns stock movements for this vendor's items.
    Supports ?movement_type= for filtering.
    """
    serializer_class = StockMovementSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdmin]
    pagination_class = StandardPagination

    def get_queryset(self):
        vp, err = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if err:
            return StockMovement.objects.none()
        qs = StockMovement.objects.filter(
            inventory_item__product__vendor=vp
        ).select_related('inventory_item__product', 'performed_by').order_by('-created_at')
        movement_type = self.request.query_params.get('movement_type')
        if movement_type:
            qs = qs.filter(movement_type=movement_type)
        return qs

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)


class VendorPurchaseOrdersView(generics.ListCreateAPIView):
    """
    GET  /api/inventory/vendor/<vendor_uuid>/purchase-orders/ — authenticated owner or administrator only.
    POST /api/inventory/vendor/<vendor_uuid>/purchase-orders/ — JWT required; vendor must own vendor_uuid.
         supplier is auto-set from the URL; do not include it in the request body.
    Supports ?status= for GET filtering.
    """
    pagination_class = StandardPagination

    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsVendorOrAdmin()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return VendorPurchaseOrderCreateSerializer
        return PurchaseOrderSerializer

    def get_queryset(self):
        vp, err = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if err:
            return PurchaseOrder.objects.none()
        qs = PurchaseOrder.objects.filter(
            supplier=vp
        ).select_related('supplier', 'warehouse', 'created_by').prefetch_related('line_items')
        po_status = self.request.query_params.get('status')
        if po_status:
            qs = qs.filter(status=po_status)
        return qs

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        vp, err = _resolve_vendor(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(supplier=vp, created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VendorWarehousesView(generics.ListCreateAPIView):
    """
    GET  /api/inventory/vendor/<vendor_uuid>/warehouses/ — authenticated owner or administrator only.
         Returns warehouses that hold this vendor's inventory items.
    POST /api/inventory/vendor/<vendor_uuid>/warehouses/ — JWT required; vendor must own vendor_uuid.
         Creates a new warehouse.
    """
    serializer_class = WarehouseSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsVendorOrAdmin()]

    def get_queryset(self):
        vp, err = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if err:
            return Warehouse.objects.none()
        return Warehouse.objects.filter(vendor=vp, is_active=True)

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        vp, err = _resolve_vendor(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(vendor=vp, created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VendorStockAlertsView(generics.ListCreateAPIView):
    """
    GET  /api/inventory/vendor/<vendor_uuid>/alerts/ — authenticated owner or administrator only.
    POST /api/inventory/vendor/<vendor_uuid>/alerts/ — JWT required; vendor must own vendor_uuid.
         inventory_item in the request body must belong to this vendor's products.
    Supports ?status= and ?alert_type= for GET filtering.
    """
    serializer_class = StockAlertSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsVendorOrAdmin()]

    def get_queryset(self):
        vp, err = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if err:
            return StockAlert.objects.none()
        qs = StockAlert.objects.filter(
            inventory_item__product__vendor=vp
        ).select_related('inventory_item__product', 'inventory_item__warehouse')
        alert_status = self.request.query_params.get('status')
        if alert_status:
            qs = qs.filter(status=alert_status)
        alert_type = self.request.query_params.get('alert_type')
        if alert_type:
            qs = qs.filter(alert_type=alert_type)
        return qs

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        vp, err = _resolve_vendor(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        item_id = request.data.get('inventory_item')
        try:
            item = InventoryItem.objects.select_related('product__vendor').get(id=item_id)
        except InventoryItem.DoesNotExist:
            return Response({'error': 'Inventory item not found.'}, status=status.HTTP_404_NOT_FOUND)
        if item.product.vendor != vp:
            return Response(
                {'error': 'Inventory item does not belong to this vendor.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)
