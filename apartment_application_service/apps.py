from django.apps import AppConfig


class ApartmentApplicationServiceConfig(AppConfig):
    name = "apartment_application_service"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import apartment_application_service.notifications  # noqa
