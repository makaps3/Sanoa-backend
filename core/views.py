from django.db import DatabaseError, connection
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])  # load-balancer probes would otherwise hit the anon rate limit
def health(request):
    """Liveness + database check for Azure / load-balancer health probes."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            connected = cursor.fetchone()[0] == 1
    except DatabaseError:
        connected = False

    return Response(
        {
            "message": "Existing Django project is running on Azure!",
            "database": "connected" if connected else "not connected",
        },
        status=status.HTTP_200_OK if connected else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
