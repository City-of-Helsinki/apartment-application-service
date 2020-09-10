from django.apps import AppConfig


class ApartmentApplicationServiceConfig(AppConfig):
    name = "apartment_application_service"

    def ready(self):
        import apartment_application_service.notifications  # noqa
