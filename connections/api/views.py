import logging

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from application_form.permissions import DrupalAuthentication, IsDrupalServer
from connections.api.serializers import MappedApartmentSerializer
from connections.enums import (
    OikotieHousingCompanyRequiredFields,
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

    @action(methods=["get"], detail=False, url_path="integration_status")
    def integration_status(self, request):
        apartments_to_etuovi = get_apartments_for_etuovi()
        apartments_to_oikotie = get_apartments_for_oikotie()

        apartments = {
            "etuovi": {"success": [], "fail": []},
            "oikotie": {"success": [], "fail": []},
        }

        # Validate Etuovi apartments
        for apartment in apartments_to_etuovi:
            ownership_type = getattr(apartment, "project_ownership_type", None)
            required_fields_enum = get_etuovi_required_fields_for_ownership_type(
                ownership_type
            )
            missing_fields = validate_apartment_required_fields(
                apartment, required_fields_enum
            )
            apartment_data = {
                "uuid": str(apartment.uuid),
                "project_uuid": getattr(apartment, "project_uuid", None),
                "project_housing_company": getattr(
                    apartment, "project_housing_company", None
                ),
                "apartment_address": getattr(
                    apartment, "apartment_address", None
                ),
                "project_url": getattr(apartment, "project_url", None),
                "url": getattr(apartment, "url", None),
                "missing_fields": missing_fields if missing_fields else [],
            }
            if missing_fields:
                apartments["etuovi"]["fail"].append(apartment_data)
            else:
                apartments["etuovi"]["success"].append(apartment_data)

        # Validate Oikotie apartments
        for apartment in apartments_to_oikotie:
            ownership_type = getattr(apartment, "project_ownership_type", None)
            
            # Validate housing company required fields
            missing_housing_company_fields = validate_apartment_required_fields(
                apartment, OikotieHousingCompanyRequiredFields
            )
            
            # Validate apartment required fields
            required_fields_enum = get_oikotie_required_fields_for_ownership_type(
                ownership_type
            )
            missing_apartment_fields = validate_apartment_required_fields(
                apartment, required_fields_enum
            )
            
            # Combine missing fields from both validations
            missing_fields = missing_housing_company_fields + missing_apartment_fields
            
            apartment_data = {
                "uuid": str(apartment.uuid),
                "project_uuid": getattr(apartment, "project_uuid", None),
                "project_housing_company": getattr(
                    apartment, "project_housing_company", None
                ),
                "apartment_address": getattr(
                    apartment, "apartment_address", None
                ),
                "project_url": getattr(apartment, "project_url", None),
                "url": getattr(apartment, "url", None),
                "missing_fields": missing_fields if missing_fields else [],
            }
            if missing_fields:
                apartments["oikotie"]["fail"].append(apartment_data)
            else:
                apartments["oikotie"]["success"].append(apartment_data)

        return Response(apartments, status=status.HTTP_200_OK)
