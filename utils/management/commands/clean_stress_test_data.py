from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apartment.models import Apartment, Identifier, Project
from application_form.models import Application, ApplicationApartment
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
        other_application_apartment_pks = list(
            ApplicationApartment.objects.exclude(
                application__in=applications
            ).values_list("apartment", flat=True)
        )
        apartments = Apartment.objects.filter(
            pk__in=list(
                application_apartments.values_list("apartment__pk", flat=True).exclude(
                    pk__in=other_application_apartment_pks
                )
            )
        )
        other_apartments = Apartment.objects.filter(
            pk__in=list(
                application_apartments.values_list("apartment").filter(
                    pk__in=other_application_apartment_pks
                )
            )
        )
        projects = Project.objects.filter(apartments__pk__in=apartments).exclude(
            apartments__pk__in=other_apartments
        )
        other_projects = Project.objects.filter(apartments__pk__in=other_apartments)
        identifiers = Identifier.objects.filter(
            Q(project__in=projects) | Q(apartment__in=apartments)
        ).exclude(Q(project__in=other_projects) | Q(apartment__in=other_apartments))

        # Remove the test data
        with transaction.atomic():
            projects.delete()
            apartments.delete()
            identifiers.delete()
            application_apartments.delete()
            applications.delete()
            users.delete()
            profiles.delete()
            audit_logs.delete()
