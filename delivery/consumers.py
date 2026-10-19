"""
WebSocket consumers for the delivery app.

Channels:
  ws/delivery/driver/jobs/         — driver receives incoming job offers
  ws/delivery/track/<job_id>/      — customer receives live GPS + status updates
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class DriverJobConsumer(AsyncWebsocketConsumer):
    """
    Drivers connect here to receive new job offers in real time.
    Group name: driver_jobs_<driver_id>

    Events pushed:
      new_job   — enriched job offer with distances, ETAs, order summary
      job_update — status change on a job the driver is handling
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        if getattr(user, 'user_type', None) != 'driver':
            await self.close(code=4003)
            return

        self.driver_id = await self._get_driver_id(user)
        if not self.driver_id:
            await self.close(code=4003)
            return

        self.group_name = f"driver_jobs_{self.driver_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send pending jobs snapshot so the driver sees any queued offers
        snapshot = await self._get_pending_jobs_snapshot(user)
        if snapshot:
            await self.send(text_data=json.dumps({
                'type': 'pending_jobs',
                'jobs': snapshot,
            }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass  # read-only consumer

    async def new_job(self, event):
        await self.send(text_data=json.dumps(event))

    async def job_update(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def _get_driver_id(self, user):
        from .models import DeliveryDriver
        try:
            driver = DeliveryDriver.objects.get(user=user)
            return driver.id
        except DeliveryDriver.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_pending_jobs_snapshot(self, user):
        """
        Return enriched pending-job offers for this driver so they see
        any queued jobs the moment they come online.
        """
        from .models import DeliveryDriver, DeliveryJob
        from .services import haversine_km, estimate_minutes, get_order_details, DISPATCH_RADIUS_KM

        try:
            driver = DeliveryDriver.objects.get(user=user)
        except DeliveryDriver.DoesNotExist:
            return []

        if not (driver.current_latitude and driver.current_longitude):
            return []

        pending_jobs = (
            DeliveryJob.objects
            .filter(status='pending')
            .exclude(declined_by=driver)
            .select_related('customer', 'retail_order', 'restaurant_order')
        )

        vehicle = driver.vehicle_type or 'motorbike'
        result = []

        for job in pending_jobs:
            if not (job.pickup_latitude and job.pickup_longitude):
                continue

            d = haversine_km(
                driver.current_latitude, driver.current_longitude,
                job.pickup_latitude, job.pickup_longitude,
            )
            if d > DISPATCH_RADIUS_KM:
                continue

            result.append({
                'job_id':                    str(job.id),
                'status':                    job.status,
                'fare_amount':               str(job.fare_amount),
                'pickup_latitude':           str(job.pickup_latitude),
                'pickup_longitude':          str(job.pickup_longitude),
                'dropoff_latitude':          str(job.dropoff_latitude),
                'dropoff_longitude':         str(job.dropoff_longitude),
                'pickup_to_dropoff_km':      str(job.distance_km or '0.00'),
                'pickup_to_dropoff_minutes': estimate_minutes(job.distance_km, vehicle),
                'driver_to_pickup_km':       str(d),
                'driver_to_pickup_minutes':  estimate_minutes(d, vehicle),
                'order':                     get_order_details(job),
            })

        return result


class DeliveryTrackingConsumer(AsyncWebsocketConsumer):
    """
    Customers (and drivers) connect to track a specific delivery job.
    Group name: delivery_job_<job_id>

    Events pushedalle
      snapshot       — full job state sent on connect
      location_update — driver GPS position with speed / heading / ETAs
      job_update      — status change (accepted, picked_up, delivered …)
    """

    async def connect(self):
        self.job_id = self.scope['url_route']['kwargs']['job_id']
        self.group_name = f"delivery_job_{self.job_id}"

        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        allowed = await self._check_access(user)
        if not allowed:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send current job state on connect
        snapshot = await self._get_job_snapshot()
        await self.send(text_data=json.dumps({'type': 'snapshot', **snapshot}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass  # read-only consumer

    async def location_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def job_update(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def _check_access(self, user):
        from .models import DeliveryJob
        try:
            job = DeliveryJob.objects.get(id=self.job_id)
        except DeliveryJob.DoesNotExist:
            return False
        if user.is_staff:
            return True
        if job.customer_id == user.id:
            return True
        if job.driver and job.driver.user_id == user.id:
            return True
        return False

    @database_sync_to_async
    def _get_job_snapshot(self):
        """
        Full snapshot sent to connecting client on connect.

        All coordinates are floats so Flutter can parse them with (num?) cast.
        Includes nested driver_location, pickup, and dropoff dicts so the
        Flutter provider can extract positions without additional parsing.
        """
        from .models import DeliveryJob
        from .services import build_trip_info

        try:
            job = DeliveryJob.objects.select_related('driver').get(id=self.job_id)
        except DeliveryJob.DoesNotExist:
            return {'error': 'Job not found'}

        driver = job.driver

        def _f(v):
            """Decimal/str → float, or None."""
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        snapshot = {
            'job_id': str(job.id),
            'status': job.status,
            # Nested driver_location dict — Flutter provider reads this key
            'driver_location': {
                'latitude':  _f(driver.current_latitude)  if driver else None,
                'longitude': _f(driver.current_longitude) if driver else None,
            },
            # Nested pickup/dropoff dicts with float coords
            'pickup': {
                'latitude':  _f(job.pickup_latitude),
                'longitude': _f(job.pickup_longitude),
            },
            'dropoff': {
                'latitude':  _f(job.dropoff_latitude),
                'longitude': _f(job.dropoff_longitude),
            },
        }

        # Full trip details only meaningful once a driver is assigned
        if driver:
            try:
                snapshot['trip'] = build_trip_info(driver, job)
            except Exception:
                pass   # non-fatal — partial snapshot is still useful

        return snapshot
