from rest_framework import serializers

from application_form.models import HasoApplication, HitasApplication


class HasoSerializer(serializers.ModelSerializer):
    class Meta:
        model = HasoApplication
        fields = "__all__"


class HitasSerializer(serializers.ModelSerializer):
    class Meta:
        model = HitasApplication
        fields = "__all__"
