from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User, Company


class CompanyBriefSerializer(serializers.ModelSerializer):
    """Lightweight company representation embedded inside UserSerializer."""

    class Meta:
        model = Company
        fields = ('id', 'name')


class UserSerializer(serializers.ModelSerializer):
    """Full user representation returned from /me/ and embedded in auth responses."""

    company = CompanyBriefSerializer(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'company')
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    """Validates username + password and returns the authenticated user object."""

    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        user = authenticate(
            request=self.context.get('request'),
            username=username,
            password=password,
        )

        if user is None:
            raise serializers.ValidationError(
                'Invalid credentials. Please check your username and password.',
                code='authorization',
            )

        if not user.is_active:
            raise serializers.ValidationError(
                'This account has been deactivated.',
                code='authorization',
            )

        # Attach user to validated data so the view can retrieve it cleanly
        attrs['user'] = user
        return attrs
