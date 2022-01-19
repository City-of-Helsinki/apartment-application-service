from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from application_form.models.application import Application, ApplicationApartment
from audit_log.models import AuditLog
from users.models import Profile, User


class Command(BaseCommand):
    help = "Clean stress test data"

    def handle(self, *args, **options):
        # Gather the test data to remove
        profiles = Profile.objects.filter(email__startswith="TestUser-")
        users = User.objects.filter(profile__in=profiles)
        profile_ids = map(str, profiles.values_list("pk", flat=True))
        audit_logs = AuditLog.objects.filter(
            Q(message__audit_event__actor__profile_id__in=profile_ids)
            | Q(message__audit_event__target__id__in=profile_ids)
        )
        applications = Application.objects.filter(profile__in=profiles)
        application_apartments = ApplicationApartment.objects.filter(
            application__in=applications
        )

        # Remove the test data
        with transaction.atomic():
            application_apartments.delete()
            applications.delete()
            users.delete()
            profiles.delete()
            audit_logs.delete()
