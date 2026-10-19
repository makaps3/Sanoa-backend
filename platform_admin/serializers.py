from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import AdminProfile, AdminInvitation, PlatformFee, ROLE_PERMISSIONS

User = get_user_model()


class AdminProfileSerializer(serializers.ModelSerializer):
    """Full read serializer."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    full_name = serializers.SerializerMethodField()
    invited_by_email = serializers.SerializerMethodField()

    class Meta:
        model = AdminProfile
        fields = [
            'id', 'user', 'user_email', 'full_name',
            'role', 'department', 'role_title',
            'work_email', 'profile_photo', 'status',
            'invited_by', 'invited_by_email',
            'permissions', 'last_login_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'user_email', 'full_name',
            'invited_by', 'invited_by_email',
            'permissions', 'last_login_at',
            'created_at', 'updated_at',
        ]

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    def get_invited_by_email(self, obj):
        if obj.invited_by:
            return obj.invited_by.user.email
        return None


class AdminProfileCreateSerializer(serializers.ModelSerializer):
    """Used when an admin self-registers their profile (POST /api/platform-admin/profile/)."""

    class Meta:
        model = AdminProfile
        fields = [
            'role', 'department', 'role_title',
            'work_email', 'profile_photo',
        ]

    def validate(self, attrs):
        user = self.context['request'].user
        if not user.is_superuser:
            raise serializers.ValidationError('Accept your administrator invitation to create a profile.')
        if user.user_type != 'admin':
            raise serializers.ValidationError('Only users with admin account type can create an admin profile.')
        if AdminProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError('You already have an admin profile.')
        return attrs

    def create(self, validated_data):
        profile = AdminProfile(**validated_data, user=self.context['request'].user)
        profile.seed_permissions()
        profile.save()
        return profile


class AdminProfileUpdateSerializer(serializers.ModelSerializer):
    """Self-update of non-sensitive fields."""

    class Meta:
        model = AdminProfile
        fields = ['role_title', 'work_email', 'profile_photo', 'department']


class AdminPermissionOverrideSerializer(serializers.Serializer):
    """Super Admin overrides individual permission keys on a profile."""
    permissions = serializers.DictField(child=serializers.BooleanField())

    def validate_permissions(self, value):
        valid_keys = set(ROLE_PERMISSIONS['super_admin'].keys())
        bad = set(value.keys()) - valid_keys
        if bad:
            raise serializers.ValidationError(f"Unknown permission keys: {bad}")
        return value

    def update(self, instance, validated_data):
        instance.permissions.update(validated_data['permissions'])
        instance.save(update_fields=['permissions'])
        return instance


class AdminInvitationSerializer(serializers.ModelSerializer):
    invited_by_email = serializers.CharField(source='invited_by.user.email', read_only=True)
    accepted_by_email = serializers.SerializerMethodField()

    class Meta:
        model = AdminInvitation
        fields = [
            'id', 'invited_by', 'invited_by_email',
            'email', 'role', 'department',
            'token', 'status', 'expires_at',
            'accepted_by', 'accepted_by_email',
            'created_at',
        ]
        read_only_fields = [
            'id', 'invited_by', 'invited_by_email',
            'token', 'status', 'expires_at',
            'accepted_by', 'accepted_by_email',
            'created_at',
        ]

    def get_accepted_by_email(self, obj):
        if obj.accepted_by:
            return obj.accepted_by.user.email
        return None


class SendInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=[r[0] for r in AdminInvitation._meta.get_field('role').choices])
    department = serializers.ChoiceField(choices=[d[0] for d in AdminInvitation._meta.get_field('department').choices])

    def validate_email(self, value):
        from django.utils import timezone
        existing = User.objects.filter(email__iexact=value).first()
        if existing and (existing.user_type != 'admin' or AdminProfile.objects.filter(user=existing).exists()):
            raise serializers.ValidationError('This email already belongs to an account with an assigned role.')
        if AdminInvitation.objects.filter(email__iexact=value, status='pending', expires_at__gt=timezone.now()).exists():
            raise serializers.ValidationError('A pending invitation already exists for this email.')
        return value

    def validate_role(self, value):
        if value == 'super_admin':
            raise serializers.ValidationError('Cannot invite a Super Admin via invitation.')
        return value


class AcceptInvitationSerializer(serializers.Serializer):
    role_title = serializers.CharField(max_length=100, required=False, allow_blank=True)
    work_email = serializers.EmailField()
    profile_photo = serializers.ImageField(required=False, allow_null=True)

    def validate_work_email(self, value):
        if AdminProfile.objects.filter(work_email=value).exists():
            raise serializers.ValidationError('This work email is already in use.')
        return value


# ── Platform Fee ──────────────────────────────────────────────────────────────

class PlatformFeeSerializer(serializers.ModelSerializer):
    """Read/write serializer for PlatformFee.

    Returns both the raw min/max decimals (so the frontend can render
    inline editors) and pre-formatted `*_range` strings the dashboard
    table can drop straight into a column without rebuilding the
    `5%-10%` literal client-side.
    """
    business_type_display = serializers.CharField(
        source='get_business_type_display', read_only=True,
    )
    customer_service_fee_range = serializers.CharField(read_only=True)
    merchant_commission_range = serializers.CharField(read_only=True)
    delivery_fee_range = serializers.CharField(read_only=True)
    updated_by_email = serializers.SerializerMethodField()

    class Meta:
        model = PlatformFee
        fields = [
            'id', 'business_type', 'business_type_display',
            'customer_service_fee_min', 'customer_service_fee_max',
            'customer_service_fee_percent',
            'customer_service_fee_range',
            'merchant_commission_min', 'merchant_commission_max',
            'merchant_commission_percent',
            'merchant_commission_range',
            'delivery_fee_min', 'delivery_fee_max',
            'delivery_fee_percent', 'delivery_fee_range',
            'notes', 'is_active',
            'updated_by', 'updated_by_email',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'business_type_display',
            'customer_service_fee_range',
            'merchant_commission_range',
            'delivery_fee_range',
            'updated_by', 'updated_by_email',
            'created_at', 'updated_at',
        ]

    def get_updated_by_email(self, obj):
        return obj.updated_by.user.email if obj.updated_by_id else None

    def validate(self, data):
        # Pull either the incoming value or the existing one — partial
        # updates only send one side of the pair.
        instance = self.instance
        def pick(field):
            if field in data:
                return data[field]
            return getattr(instance, field) if instance else None
        csf_min = pick('customer_service_fee_min')
        csf_max = pick('customer_service_fee_max')
        mc_min = pick('merchant_commission_min')
        mc_max = pick('merchant_commission_max')
        if csf_min is not None and csf_max is not None and csf_min > csf_max:
            raise serializers.ValidationError({
                'customer_service_fee_min':
                    'Lower bound must be ≤ upper bound.',
            })
        if mc_min is not None and mc_max is not None and mc_min > mc_max:
            raise serializers.ValidationError({
                'merchant_commission_min':
                    'Lower bound must be ≤ upper bound.',
            })
        # Applied percent must sit inside its range (if supplied).
        csf_applied = pick('customer_service_fee_percent')
        if csf_applied not in (None, 0) and csf_min is not None and csf_max is not None:
            if not (csf_min <= csf_applied <= csf_max):
                raise serializers.ValidationError({
                    'customer_service_fee_percent':
                        f'Must be between {csf_min}% and {csf_max}%.',
                })
        mc_applied = pick('merchant_commission_percent')
        if mc_applied not in (None, 0) and mc_min is not None and mc_max is not None:
            if not (mc_min <= mc_applied <= mc_max):
                raise serializers.ValidationError({
                    'merchant_commission_percent':
                        f'Must be between {mc_min}% and {mc_max}%.',
                })
        # Delivery commission band — 0-5 %, validated the same way.
        df_min = pick('delivery_fee_min')
        df_max = pick('delivery_fee_max')
        if df_min is not None and df_max is not None and df_min > df_max:
            raise serializers.ValidationError({
                'delivery_fee_min':
                    'Lower bound must be ≤ upper bound.',
            })
        df_applied = pick('delivery_fee_percent')
        if df_applied not in (None, 0) and df_min is not None and df_max is not None:
            if not (df_min <= df_applied <= df_max):
                raise serializers.ValidationError({
                    'delivery_fee_percent':
                        f'Must be between {df_min}% and {df_max}%.',
                })
        return data
