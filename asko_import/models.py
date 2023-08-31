from django.contrib.contenttypes.models import ContentType
from django.db import models


class AsKoLink(models.Model):
    asko_id = models.IntegerField()
    object_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id_int = models.BigIntegerField(null=True)
    object_id_uuid = models.UUIDField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_object(self):
        model = self.object_type.model_class()
        pk = self.object_id_int or self.object_id_uuid
        return model.objects.get(pk=pk) if pk else None

    @classmethod
    def store(cls, asko_id, obj):
        model = type(obj)
        return cls.objects.update_or_create(
            asko_id=asko_id,
            object_type=ContentType.objects.get_for_model(model),
            defaults={
                cls.get_id_field_name(model): obj.pk,
            },
        )[0]

    @classmethod
    def get_map_for_model(cls, model):
        object_type = ContentType.objects.get_for_model(model)
        asko_links = cls.objects.filter(object_type=object_type)
        id_field_name = cls.get_id_field_name(model)
        return asko_links.values_list("asko_id", id_field_name)

    @classmethod
    def get_objects_of_model(cls, model, object_ids=None):
        object_type = ContentType.objects.get_for_model(model)
        asko_links = cls.objects.filter(object_type=object_type)
        if object_ids is None:
            return asko_links
        id_field_name = cls.get_id_field_name(model)
        return asko_links.filter(**{f"{id_field_name}__in": object_ids})

    @classmethod
    def get_id_field_name(cls, model):
        id_field = model._meta.get_field("id")
        if isinstance(id_field, models.IntegerField):
            return "object_id_int"
        elif isinstance(id_field, models.UUIDField):
            return "object_id_uuid"
        pk_type = type(id_field).__name__
        raise TypeError(f"Unsupported pk type {pk_type} for model {model}")

    class Meta:
        unique_together = [
            ("object_type", "asko_id"),
        ]
        index_together = [
            ("object_type", "asko_id", "object_id_int"),
            ("object_type", "asko_id", "object_id_uuid"),
        ]

    def __str__(self):
        return f"AsKo link {self.object_type.model} asko_id={self.asko_id}"
