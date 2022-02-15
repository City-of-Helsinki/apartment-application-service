from users.api.serializers import ProfileSerializerBase


class ProfileSerializer(ProfileSerializerBase):
    class Meta(ProfileSerializerBase.Meta):
        fields = ProfileSerializerBase.Meta.fields + ("national_identification_number",)
