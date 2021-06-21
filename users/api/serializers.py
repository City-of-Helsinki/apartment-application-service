import logging
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework.fields import CharField, EmailField, UUIDField
from rest_framework.serializers import ModelSerializer, Serializer
from rest_framework_simplejwt.serializers import (
    PasswordField,
    TokenObtainPairSerializer,
)
from typing import Optional
from uuid import UUID

from users.masking import unmask_string, unmask_uuid
from users.models import Profile

_logger = logging.getLogger(__name__)


class ProfileSerializer(ModelSerializer):
    id = UUIDField(source="pk")
    email = EmailField(source="user.email")
    first_name = CharField(source="user.first_name", max_length=30)
    last_name = CharField(source="user.last_name", max_length=150)

    class Meta:
        model = Profile
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "street_address",
            "date_of_birth",
            "city",
            "postal_code",
            "contact_language",
        ]

    @transaction.atomic
    def create(self, validated_data):
        _logger.info("Creating a new profile")
        user = get_user_model().objects.create(**validated_data.pop("user"))
        profile = Profile.objects.create(user=user, **validated_data)
        _logger.info(f"Profile {profile.pk} created")
        return profile

    @transaction.atomic
    def update(self, instance, validated_data):
        _logger.info(f"Updating profile {instance.pk}")
        user = instance.user
        user_data = validated_data.pop("user", {})
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        _logger.info(f"Profile {instance.pk} updated")
        return instance

    class CreateResponseSerializer(Serializer):
        profile_id = CharField()
        password = CharField()


class MaskedTokenObtainPairSerializer(TokenObtainPairSerializer):
    profile_id_field = "profile_id"
    password_field = "password"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.clear()
        self.fields[self.profile_id_field] = CharField()
        self.fields[self.password_field] = PasswordField()

    def validate(self, attrs):
        """
        Validate the user credentials. The masked "username" (profile ID) should be
        given in the "profile_id" field, and the masked password in the "password"
        field. Both of these will be unmasked and then used to authenticate. The
        profile ID is used to look up the corresponding username.
        """
        profile_id = unmask_uuid(attrs.get(self.profile_id_field, ""))
        attrs[self.username_field] = self._get_username_by_profile_id(profile_id)
        attrs[self.password_field] = unmask_string(attrs.get(self.password_field, ""))
        return super().validate(attrs)

    def _get_username_by_profile_id(self, profile_id: UUID) -> Optional[str]:
        """
        Look up a username by profile ID. This is to allow us to leverage the standard
        Django model authentication backend with username/password, instead of having
        to write a custom one that deals with profile IDs and passwords.
        """
        try:
            user = get_user_model().objects.get(profile__pk=profile_id)
            return user.username
        except ObjectDoesNotExist:
            return None

    class ResponseSerializer(Serializer):
        refresh = CharField()
        access = CharField()
