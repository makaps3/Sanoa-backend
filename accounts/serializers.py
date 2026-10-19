"""
Serializers for accounts app
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import CustomerProfile, APIToken

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'phone_number', 'user_type', 'is_verified', 'date_of_birth',
            'is_active', 'date_joined', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user_type', 'is_verified', 'is_active',
                            'date_joined', 'created_at', 'updated_at']


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for User model"""

    customer_profile = serializers.SerializerMethodField()
    individual_vendor_profile = serializers.SerializerMethodField()
    business_vendor_profile = serializers.SerializerMethodField()
    addresses = serializers.SerializerMethodField()
    vendor_employment = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'phone_number', 'user_type', 'is_verified', 'date_of_birth',
            'is_active', 'must_change_password',
            'customer_profile', 'individual_vendor_profile',
            'business_vendor_profile', 'vendor_employment', 'addresses',
            'date_joined', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'email', 'user_type', 'is_verified', 'is_active',
                            'must_change_password', 'date_joined', 'created_at', 'updated_at']

    def get_vendor_employment(self, obj):
        emp = getattr(obj, 'vendor_employment', None)
        if emp is None:
            return None
        vendor = emp.vendor
        perms = emp.permissions or {}
        from business.models import VendorEmployee
        return {
            'id': str(emp.id),
            'is_manager': emp.is_manager,
            'role_title': emp.role_title,
            'department': emp.department,
            'verification_status': emp.verification_status,
            'is_active': emp.is_active,
            'permissions': {
                k: bool(perms.get(k, False)) or emp.is_manager
                for k, _ in VendorEmployee.PERMISSION_KEYS
            },
            'vendor': {
                'id': str(vendor.id),
                'name': vendor.name,
                'profile_type': vendor.profile_type,
            },
        }

    def get_customer_profile(self, obj):
        if hasattr(obj, 'customer_profile'):
            return CustomerProfileSerializer(obj.customer_profile).data
        return None

    def get_individual_vendor_profile(self, obj):
        if hasattr(obj, 'individual_vendor_profile'):
            from business.serializers import IndividualVendorProfileSerializer
            return IndividualVendorProfileSerializer(obj.individual_vendor_profile).data
        return None

    def get_business_vendor_profile(self, obj):
        if hasattr(obj, 'business_vendor_profile'):
            from business.serializers import BusinessVendorProfileSerializer
            return BusinessVendorProfileSerializer(obj.business_vendor_profile).data
        return None

    def get_addresses(self, obj):
        """
        For customers: return personal shipping addresses.
        For vendors: return the vendor profile's business addresses.
        """
        if obj.user_type == 'customer':
            from orders.serializers import ShippingAddressSerializer
            qs = obj.shipping_addresses.all()
            return ShippingAddressSerializer(qs, many=True).data
        vp = getattr(obj, 'vendor_profile', None)
        if vp is None:
            return []
        from business.serializers import AddressSerializer
        return AddressSerializer(vp.addresses.all(), many=True).data


class UserRegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            'email', 'username', 'first_name', 'last_name',
            'phone_number', 'user_type', 'password', 'password_confirm',
        ]

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError("Passwords do not match.")
        role = data.get('user_type', 'customer')
        if role == 'employee':
            raise serializers.ValidationError({'user_type': 'Employees must be invited by their vendor.'})
        if role == 'admin':
            from platform_admin.models import AdminInvitation
            if not AdminInvitation.objects.filter(
                email__iexact=data['email'], status='pending', expires_at__gt=timezone.now()
            ).exists():
                raise serializers.ValidationError({'user_type': 'An active administrator invitation is required.'})
        try:
            validate_password(data['password'], User(**{k: v for k, v in data.items() if k != 'password'}))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages})
        return data

    def create(self, validated_data):
        password = validated_data.pop('password')
        return User.objects.create_user(password=password, **validated_data)


class CustomerProfileSerializer(serializers.ModelSerializer):
    """Serializer for CustomerProfile model"""

    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = CustomerProfile
        fields = [
            'id', 'user_email', 'avatar', 'gender', 'bio',
            'interest_categories', 'latitude', 'longitude',
            'preferred_language', 'newsletter_subscription',
            'sms_notifications', 'email_notifications',
            'loyalty_points', 'member_since', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'loyalty_points', 'member_since', 'created_at', 'updated_at']


# =============================================================================
# API Token Serializers
# =============================================================================

class APITokenSerializer(serializers.ModelSerializer):
    """Serializer for listing existing API tokens (never exposes the raw token)"""

    is_expired = serializers.BooleanField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = APIToken
        fields = [
            'id', 'name', 'prefix', 'scope', 'is_active',
            'expires_at', 'is_expired', 'is_valid',
            'last_used_at', 'last_used_ip', 'total_requests',
            'created_at',
        ]
        read_only_fields = [
            'id', 'prefix', 'last_used_at', 'last_used_ip',
            'total_requests', 'created_at',
        ]


class APITokenCreatedSerializer(APITokenSerializer):
    """The secret exists only on the newly created in-memory instance."""

    token = serializers.CharField(source='_raw_token', read_only=True)

    class Meta(APITokenSerializer.Meta):
        fields = [*APITokenSerializer.Meta.fields, 'token']


class APITokenCreateSerializer(serializers.Serializer):
    """Serializer for creating a new API token. Returns the raw token once."""

    name = serializers.CharField(max_length=100)
    scope = serializers.ChoiceField(choices=APIToken.SCOPE_CHOICES, default='full')
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_expires_at(self, value):
        from django.utils import timezone
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError('Expiry must be in the future.')
        return value

    def validate_name(self, value):
        user = self.context['request'].user
        if APIToken.objects.filter(user=user, name=value, is_active=True).exists():
            raise serializers.ValidationError("You already have an active token with this name.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        raw_token, token_hash, prefix = APIToken.generate_token()

        token = APIToken.objects.create(
            user=user,
            name=validated_data['name'],
            token_hash=token_hash,
            prefix=prefix,
            scope=validated_data.get('scope', 'full'),
            expires_at=validated_data.get('expires_at'),
        )
        token._raw_token = raw_token
        return token
