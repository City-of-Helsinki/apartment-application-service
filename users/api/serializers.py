import logging
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.fields import CharField, EmailField
from rest_framework.serializers import ModelSerializer

from users.models import Profile

_logger = logging.getLogger(__name__)


class ProfileSerializer(ModelSerializer):
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
            "address",
            "date_of_birth",
            "city",
            "postal_code",
            "right_of_residence",
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
