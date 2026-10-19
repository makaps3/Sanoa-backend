"""
Driver analytics views — driver sees only their own data.
Endpoints live under /api/delivery/driver/analytics/.
Supports ?period=today|week|month|year.
"""
import datetime

import numpy as np
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.insights import (
    driver_earnings_insights,
    driver_overview_insights,
    driver_performance_insights,
)


def _get_driver(request):
    return getattr(request.user, 'driver_profile', None)


def _date_range(request):
    period = request.query_params.get('period', 'month')
    from_str = request.query_params.get('from')
    to_str = request.query_params.get('to')
    now = timezone.now()

    if from_str and to_str:
        try:
            start = datetime.datetime.fromisoformat(from_str).replace(tzinfo=datetime.timezone.utc)
            end = datetime.datetime.fromisoformat(to_str).replace(tzinfo=datetime.timezone.utc)
            return start, end
        except ValueError:
            pass

    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start = now - datetime.timedelta(days=7)
    elif period == 'year':
        start = now - datetime.timedelta(days=365)
    else:
        start = now - datetime.timedelta(days=30)
    return start, now


class DriverAnalyticsOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        driver = _get_driver(request)
        if not driver:
            return Response({'detail': 'Driver profile required.'}, status=status.HTTP_403_FORBIDDEN)

        from delivery.models import DeliveryJob, DriverEarning
        from analytics.models import DriverPerformanceScore

        start, end = _date_range(request)
        jobs = DeliveryJob.objects.filter(driver=driver, created_at__gte=start, created_at__lte=end)
        completed = jobs.filter(status='delivered').count()
        total = jobs.count()

        earnings = DriverEarning.objects.filter(driver=driver, created_at__gte=start, created_at__lte=end)
        earn_agg = earnings.aggregate(
            gross=Sum('gross_amount'), commission=Sum('platform_commission'), net=Sum('net_amount'),
        )

        try:
            perf = driver.performance_score
            ml_score = {
                'score': perf.score,
                'grade': perf.grade,
                'completion_rate': perf.completion_rate,
                'on_time_rate': perf.on_time_rate,
                'avg_delivery_time_mins': perf.avg_delivery_time_mins,
                'payout_anomaly': perf.payout_anomaly,
                'scored_at': perf.scored_at,
            }
        except Exception:
            ml_score = None

        result = {
            'period': {'start': start, 'end': end},
            'deliveries': {
                'total': total,
                'completed': completed,
                'failed': jobs.filter(status__in=('cancelled', 'failed')).count(),
                'in_transit': jobs.filter(status='in_transit').count(),
                'completion_rate_percent': round(completed / total * 100, 2) if total else 0,
            },
            'earnings': {
                'gross': earn_agg['gross'] or 0,
                'platform_commission': earn_agg['commission'] or 0,
                'net': earn_agg['net'] or 0,
            },
            'rating': driver.average_rating,
            'total_deliveries_all_time': driver.total_deliveries,
            'performance_score': ml_score,
        }
        result['insights'] = driver_overview_insights(result)
        return Response(result)


class DriverEarningsAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        driver = _get_driver(request)
        if not driver:
            return Response({'detail': 'Driver profile required.'}, status=status.HTTP_403_FORBIDDEN)

        from delivery.models import DriverEarning, DriverPayout

        start, end = _date_range(request)
        earnings = DriverEarning.objects.filter(driver=driver, created_at__gte=start, created_at__lte=end)

        agg = earnings.aggregate(
            gross=Sum('gross_amount'),
            commission=Sum('platform_commission'),
            net=Sum('net_amount'),
            count=Count('id'),
        )

        status_breakdown = earnings.values('status').annotate(count=Count('id'), total=Sum('net_amount'))

        payouts = DriverPayout.objects.filter(driver=driver, created_at__gte=start, created_at__lte=end)
        payout_agg = payouts.aggregate(
            total_paid=Sum('total_net'), count=Count('id'),
        )
        payout_status = payouts.values('status').annotate(count=Count('id'), total=Sum('total_net'))

        daily = (
            earnings.extra(select={'day': "DATE(created_at)"})
            .values('day')
            .annotate(net=Sum('net_amount'), jobs=Count('id'))
            .order_by('day')
        )

        result = {
            'period': {'start': start, 'end': end},
            'earnings': {
                'total_jobs': agg['count'] or 0,
                'gross': agg['gross'] or 0,
                'platform_commission': agg['commission'] or 0,
                'net': agg['net'] or 0,
                'avg_per_job': (agg['net'] or 0) / agg['count'] if agg['count'] else 0,
            },
            'payouts': {
                'count': payout_agg['count'] or 0,
                'total_paid': payout_agg['total_paid'] or 0,
                'status_breakdown': list(payout_status),
            },
            'earnings_status_breakdown': list(status_breakdown),
            'daily_earnings': list(daily),
        }
        result['insights'] = driver_earnings_insights(result)
        return Response(result)


class DriverPerformanceAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        driver = _get_driver(request)
        if not driver:
            return Response({'detail': 'Driver profile required.'}, status=status.HTTP_403_FORBIDDEN)

        from delivery.models import DeliveryJob, DriverRating, DriverShift
        from analytics.models import DriverPerformanceScore

        start, end = _date_range(request)
        jobs = DeliveryJob.objects.filter(driver=driver, created_at__gte=start, created_at__lte=end)

        # Delivery time stats
        times = []
        for job in jobs.filter(status='delivered', accepted_at__isnull=False, delivered_at__isnull=False):
            delta = (job.delivered_at - job.accepted_at).total_seconds() / 60
            if 0 < delta < 480:
                times.append(delta)
        avg_time = round(float(np.mean(times)), 2) if times else None
        on_time = sum(1 for t in times if t <= 90)
        on_time_rate = round(on_time / len(times) * 100, 2) if times else 0

        # Ratings over period
        ratings = DriverRating.objects.filter(driver=driver, created_at__gte=start, created_at__lte=end)
        rating_agg = ratings.aggregate(avg=Avg('rating'), count=Count('id'))

        # Shifts
        shifts = DriverShift.objects.filter(driver=driver, started_at__gte=start, started_at__lte=end)
        total_shift_hours = 0
        for s in shifts.filter(ended_at__isnull=False):
            total_shift_hours += (s.ended_at - s.started_at).total_seconds() / 3600

        try:
            perf = driver.performance_score
            ml = {
                'score': perf.score,
                'grade': perf.grade,
                'payout_anomaly': perf.payout_anomaly,
                'model_version': perf.model_version,
                'scored_at': perf.scored_at,
            }
        except Exception:
            ml = None

        result = {
            'period': {'start': start, 'end': end},
            'delivery_performance': {
                'total_jobs': jobs.count(),
                'completed': jobs.filter(status='delivered').count(),
                'failed': jobs.filter(status__in=('cancelled', 'failed')).count(),
                'avg_delivery_time_mins': avg_time,
                'on_time_rate_percent': on_time_rate,
                'avg_distance_km': jobs.aggregate(avg=Avg('distance_km'))['avg'] or 0,
            },
            'ratings': {
                'avg_rating': rating_agg['avg'] or 0,
                'total_ratings': rating_agg['count'],
                'all_time_avg': driver.average_rating,
            },
            'shifts': {
                'total_shifts': shifts.count(),
                'total_hours_online': round(total_shift_hours, 2),
            },
            'ml_performance_score': ml,
        }
        result['insights'] = driver_performance_insights(result)
        return Response(result)
