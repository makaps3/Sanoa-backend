from rest_framework import serializers


class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    purpose = serializers.ChoiceField(
        choices=['verification', 'password_reset', 'login'],
        default='verification',
    )


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(required=True, max_length=6, min_length=6)
    purpose = serializers.ChoiceField(
        choices=['verification', 'password_reset', 'login'],
        required=True,
    )


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    purpose = serializers.ChoiceField(
        choices=['verification', 'password_reset', 'login'],
        default='verification',
    )
