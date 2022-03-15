from enumfields.drf import EnumField
from rest_framework import serializers
from rest_framework.fields import CharField, DateTimeField, IntegerField, UUIDField

from audit_log.enums import Operation, Role, Status
from audit_log.models import AuditLog


class ActorSerializer(serializers.Serializer):
    role = EnumField(Role)
    profile_id = UUIDField()

    class Meta:
        fields = ["role", "profile_id"]


class TargetSerializer(serializers.Serializer):
    id = UUIDField()
    type = CharField()

    class Meta:
        fields = ["id", "type"]


class AuditEventSerializer(serializers.Serializer):
    origin = CharField()
    status = EnumField(Status)
    date_time_epoch = IntegerField()
    date_time = DateTimeField()
    actor = ActorSerializer()
    operation = EnumField(Operation)
    target = TargetSerializer()

    class Meta:
        fields = [
            "origin",
            "status",
            "date_time_epoch",
            "date_time",
            "actor",
            "operation",
            "target",
        ]


class AuditLogSerializer(serializers.Serializer):
    audit_event = AuditEventSerializer()

    class Meta:
        fields = ["audit_event"]

    def create(self, validated_data):
        return AuditLog.objects.create(message=self.data)
