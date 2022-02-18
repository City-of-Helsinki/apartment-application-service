from users.api.serializers import ProfileSerializerBase


class ProfileSerializer(ProfileSerializerBase):
    class Meta(ProfileSerializerBase.Meta):
        fields = ProfileSerializerBase.Meta.fields + (
            "national_identification_number",
            "street_address",
            "postal_code",
            "city",
            "contact_language",
        )
