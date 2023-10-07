import logging
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db import models

from customer.models import Customer

from .describer import get_description


class AsKoLink(models.Model):
    asko_id = models.IntegerField()
    object_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id_int = models.BigIntegerField(null=True)
    object_id_uuid = models.UUIDField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def object_description(self) -> str:
        obj = self.get_object()
        return get_description(obj) if obj else ""

    def get_object(self) -> Optional[models.Model]:
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
        asko_links = cls.get_objects_of_model(model)
        id_field_name = cls.get_id_field_name(model)
        return asko_links.values_list("asko_id", id_field_name)

    @classmethod
    def get_ids_of_model(cls, model):
        asko_links = cls.get_objects_of_model(model)
        id_field_name = cls.get_id_field_name(model)
        return asko_links.values(id_field_name)

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
        verbose_name = "AsKo Link"
        verbose_name_plural = "AsKo Links"

    def __str__(self):
        return f"AsKo link {self.object_type.model} asko_id={self.asko_id}"


class AsKoImportLogEntry(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    message_template = models.CharField(max_length=1000)
    message = models.TextField()
    level = models.IntegerField(null=True, blank=True)
    exception = models.TextField(blank=True)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    asko_id = models.IntegerField(null=True, blank=True)
    asko_link = models.ForeignKey(
        AsKoLink,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="logs",
    )

    class Meta:
        ordering = ("created_at", "id")
        verbose_name = "AsKo Import Log Entry"
        verbose_name_plural = "AsKo Import Log Entries"

    @property
    def level_name(self):
        return logging.getLevelName(self.level) if self.level else ""

    @property
    def model(self):
        return self.content_type.model_class() if self.content_type else None

    @property
    def model_name(self):
        return self.model.__name__ if self.model else ""

    @classmethod
    def store(
        cls,
        message_template,
        message,
        level=None,
        model=None,
        asko_id=None,
        exception=None,
    ):
        """
        Store a new log entry to database.
        """
        ctype = ContentType.objects.get_for_model(model) if model else None
        asko_link = (
            AsKoLink.objects.get_or_create(object_type=ctype, asko_id=asko_id)[0]
            if ctype and asko_id
            else None
        )
        return cls.objects.create(
            message_template=message_template,
            message=message,
            level=level,
            exception=str(exception) if exception else "",
            content_type=ctype,
            asko_id=asko_id,
            asko_link=asko_link,
        )

    def __str__(self):
        prefix = ""
        if self.level:
            prefix += f"({self.level_name}) "
        if self.model_name:
            prefix += f"{self.model_name} "
        if self.asko_id:
            prefix += f"asko_id={self.asko_id} "
        if prefix:
            prefix = prefix.rstrip() + ":"

        suffix = ""
        if self.exception:
            suffix += f" ({self.exception})"

        return f"{self.created_at}: {prefix}{self.message}{suffix}"

    @property
    def object_description(self) -> str:
        asko_link = self.asko_link
        description = asko_link.object_description if asko_link else ""
        if "Duplicate key: asko_id=" in self.message:
            asko_id = self.message.split("asko_id=", 1)[1].split(" ", 1)[0]
            asko_link = AsKoLink.objects.filter(
                object_type=self.content_type, asko_id=asko_id
            ).first()
            other_desc = asko_link.object_description if asko_link else ""
            description += f" (duplicate of {other_desc})"
        elif "'customerid': '" in self.message:
            asko_id = self.message.split("'customerid': '", 1)[1].split("'", 1)[0]
            asko_link = AsKoLink.objects.filter(
                object_type=ContentType.objects.get_for_model(Customer),
                asko_id=asko_id,
            ).first()
            customer_desc = asko_link.object_description if asko_link else ""
            description += f" (customer {customer_desc})"
        return description
