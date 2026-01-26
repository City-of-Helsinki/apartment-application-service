import logging
from typing import Any

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from drf_spectacular.types import OpenApiTypes
from application_form.permissions import DrupalAuthentication, IsDrupalServer
from connections.api.serializers import MappedApartmentSerializer
from connections.enums import (
    get_etuovi_required_fields_for_ownership_type,
    get_oikotie_required_fields_for_ownership_type,
)
from connections.etuovi.services import get_apartments_for_etuovi
from connections.models import MappedApartment
from connections.oikotie.services import get_apartments_for_oikotie
from connections.utils import validate_apartment_required_fields

_logger = logging.getLogger(__name__)


class Connections(ModelViewSet):
    """
    A class for for internal communication with Drupal.
    """

    queryset = MappedApartment.objects.all()
    serializer_class = MappedApartmentSerializer
    permission_classes = [IsAuthenticated, IsDrupalServer]
    authentication_classes = [DrupalAuthentication]

    @action(methods=["get"], detail=False, url_path="get_mapped_apartments")
    def get_mapped_apartments(self, request):
        apartment_uuids = MappedApartment.objects.filter(
            mapped_etuovi=True, mapped_oikotie=True
        ).values_list("apartment_uuid", flat=True)
        apartment_uuids = [str(i) for i in apartment_uuids]

        return Response(
            apartment_uuids,
            content_type="application/json",
            status=status.HTTP_200_OK,
        )


    from drf_spectacular.utils import extend_schema, OpenApiExample

    @extend_schema(
        summary="List integration status",
        description=(
            "Retrieve a list of apartment UUIDs that have been mapped to Etuovi and Oikotie integrations."
        ),
        responses={
            (200, "application/json"): OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                "Integration status example",
                value={
                    "etuovi": {
                        "success": [
                            {
                                "uuid": "uuid-etuovi-success-1",
                                "project_uuid": "project-uuid-1",
                                "project_housing_company": "Housing Company One",
                                "apartment_address": "Street 1 A 1",
                                "project_url": "https://asuntotuotanto.docker.so/projects/one",
                                "url": "https://asuntotuotanto.docker.so/apartments/one",
                                "missing_fields": [],
                                "last_mapped": {
                                    "etuovi": "2024-05-10T11:00:00.000Z",
                                    "oikotie": "2024-05-09T09:30:00.000Z"
                                },
                            },
                            {
                                "uuid": "uuid-etuovi-success-2",
                                "project_uuid": "project-uuid-2",
                                "project_housing_company": "Housing Company Two",
                                "apartment_address": "Street 2 B 2",
                                "project_url": "https://asuntotuotanto.docker.so/projects/two",
                                "url": "https://asuntotuotanto.docker.so/apartments/two",
                                "missing_fields": [],
                                "last_mapped": {
                                    "etuovi": "2024-05-08T14:00:00.000Z",
                                    "oikotie": "2024-05-08T13:00:00.000Z"
                                },
                            },
                        ],
                        "fail": [
                            {
                                "uuid": "uuid-etuovi-failure-1",
                                "project_uuid": "project-uuid-3",
                                "project_housing_company": "Housing Company Three",
                                "apartment_address": "Street 3 C 3",
                                "project_url": "https://asuntotuotanto.docker.so/projects/three",
                                "url": "https://asuntotuotanto.docker.so/apartments/three",
                                "missing_fields": ["url"],
                                "last_mapped": {
                                    "etuovi": None,
                                    "oikotie": None,
                                },
                            }
                        ]
                    },
                    "oikotie": {
                        "success": [
                            {
                                "uuid": "uuid-oikotie-success-1",
                                "project_uuid": "project-uuid-2",
                                "project_housing_company": "Housing Company Two",
                                "apartment_address": "Street 2 B 2",
                                "project_url": "https://project-example.fi/two",
                                "url": "https://apartment-example.fi/two",
                                "missing_fields": [],
                                "last_mapped": {
                                    "etuovi": "2024-05-08T14:00:00.000Z",
                                    "oikotie": "2024-05-08T13:00:00.000Z"
                                },
                            }
                        ],
                        "fail": [
                            {
                                "uuid": "uuid-oikotie-failure-1",
                                "project_uuid": "project-uuid-4",
                                "project_housing_company": "Housing Company Four",
                                "apartment_address": "Street 4 D 4",
                                "project_url": "https://project-example.fi/four",
                                "url": None,
                                "missing_fields": ["url"],
                                "last_mapped": {
                                    "etuovi": "2024-05-08T14:00:00.000Z",
                                    "oikotie": None,
                                },
                            }
                        ]
                    }
                },
            ),
        ],
    )
    @action(methods=["get"], detail=False, url_path="integration_status")
    def integration_status(self, request):
        apartments_to_etuovi = get_apartments_for_etuovi()
        apartments_to_oikotie = get_apartments_for_oikotie()

        apartments_last_mapped = MappedApartment.objects.filter(
            Q(last_mapped_to_etuovi__isnull=False)
            | Q(last_mapped_to_oikotie__isnull=False)
        ).values_list(
            "apartment_uuid", "last_mapped_to_etuovi", "last_mapped_to_oikotie"
        )

        apartments_last_mapped_dict: dict[str, dict[str, Any]] = dict(
            (
                str(apartment_uuid),
                {"etuovi": last_mapped_to_etuovi, "oikotie": last_mapped_to_oikotie},
            )
            for apartment_uuid, last_mapped_to_etuovi, last_mapped_to_oikotie
            in apartments_last_mapped
        )

        apartments = {
            "etuovi": {"success": [], "fail": []},
            "oikotie": {"success": [], "fail": []},
        }

        # Validate Etuovi apartments
        for apartment in apartments_to_etuovi:
            ownership_type = getattr(apartment, "project_ownership_type", None)
            required_fields = get_etuovi_required_fields_for_ownership_type(
                ownership_type
            )

            missing_fields = validate_apartment_required_fields(
                apartment, required_fields
            )
            apartment_data = {
                "uuid": str(apartment.uuid),
                "project_uuid": getattr(apartment, "project_uuid", None),
                "project_housing_company": getattr(
                    apartment, "project_housing_company", None
                ),
                "apartment_address": getattr(apartment, "apartment_address", None),
                "project_url": getattr(apartment, "project_url", None),
                "url": getattr(apartment, "url", None),
                "missing_fields": missing_fields if missing_fields else [],
                "last_mapped": apartments_last_mapped_dict.get(
                    str(apartment.uuid), {"etuovi": None, "oikotie": None}
                ),
            }

            if missing_fields:
                apartments["etuovi"]["fail"].append(apartment_data)
            else:
                apartments["etuovi"]["success"].append(apartment_data)

        # Validate Oikotie apartments
        for apartment in apartments_to_oikotie:
            ownership_type = getattr(apartment, "project_ownership_type", None)

            required_fields_housing_company = (
                get_oikotie_required_fields_for_ownership_type(ownership_type)
            )

            # Validate housing company required fields
            missing_housing_company_fields = validate_apartment_required_fields(
                apartment, required_fields_housing_company
            )

            # Validate apartment required fields
            required_fields_apartment = get_oikotie_required_fields_for_ownership_type(
                ownership_type
            )
            missing_apartment_fields = validate_apartment_required_fields(
                apartment, required_fields_apartment
            )

            # Combine missing fields from both validations
            missing_fields = missing_housing_company_fields + missing_apartment_fields

            apartment_data = {
                "uuid": str(apartment.uuid),
                "project_uuid": getattr(apartment, "project_uuid", None),
                "project_housing_company": getattr(
                    apartment, "project_housing_company", None
                ),
                "apartment_address": getattr(apartment, "apartment_address", None),
                "project_url": getattr(apartment, "project_url", None),
                "url": getattr(apartment, "url", None),
                "missing_fields": missing_fields if missing_fields else [],
                "last_mapped": apartments_last_mapped_dict.get(
                    str(apartment.uuid), {"etuovi": None, "oikotie": None}
                ),
            }

            if missing_fields:
                apartments["oikotie"]["fail"].append(apartment_data)
            else:
                apartments["oikotie"]["success"].append(apartment_data)

        return Response(apartments, status=status.HTTP_200_OK)
