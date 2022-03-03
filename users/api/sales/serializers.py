from rest_framework.fields import UUIDField

from users.api.serializers import ProfileSerializerBase


class ProfileSerializer(ProfileSerializerBase):
    id = UUIDField(source="pk", read_only=True)

    class Meta(ProfileSerializerBase.Meta):
        fields = ProfileSerializerBase.Meta.fields + (
            "national_identification_number",
            "street_address",
            "postal_code",
            "city",
            "contact_language",
            "date_of_birth",
        )
