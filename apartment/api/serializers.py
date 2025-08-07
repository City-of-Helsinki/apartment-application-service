from datetime import datetime

from django.db.models import Count, Exists, Max, OuterRef
from django.utils.functional import cached_property
from rest_framework import serializers

from apartment.api.sales.serializers import ApartmentSerializer
from apartment.elastic.queries import get_apartments
from apartment.models import ProjectExtraData
from application_form.api.sales.serializers import ProjectExtraDataSerializer
from application_form.models import ApartmentReservation, Application, LotteryEvent
from invoicing.api.serializers import ProjectInstallmentTemplateSerializer
from invoicing.models import ProjectInstallmentTemplate


class ApartmentDocumentSerializer(serializers.Serializer):
    uuid = serializers.UUIDField()
    apartment_address = serializers.CharField()
    apartment_number = serializers.CharField()
    housing_shares = serializers.CharField()
    living_area = serializers.FloatField()
    floor = serializers.IntegerField()
    floor_max = serializers.IntegerField()
    showing_times = serializers.ListField()
    apartment_structure = serializers.CharField()
    room_count = serializers.IntegerField()
    condition = serializers.CharField()
    kitchen_appliances = serializers.CharField()
    has_yard = serializers.BooleanField()
    has_terrace = serializers.BooleanField()
    has_balcony = serializers.BooleanField()
    balcony_description = serializers.CharField()
    bathroom_appliances = serializers.CharField()
    storage_description = serializers.CharField()
    has_apartment_sauna = serializers.BooleanField()
    apartment_holding_type = serializers.CharField()
    view_description = serializers.CharField()
    sales_price = serializers.IntegerField()
    debt_free_sales_price = serializers.IntegerField()
    loan_share = serializers.IntegerField()
    price_m2 = serializers.IntegerField()
    housing_company_fee = serializers.IntegerField()
    financing_fee = serializers.IntegerField()
    maintenance_fee = serializers.IntegerField()
    water_fee = serializers.IntegerField()
    water_fee_explanation = serializers.CharField()
    parking_fee = serializers.IntegerField()
    parking_fee_explanation = serializers.CharField()
    other_fees = serializers.CharField()
    services_description = serializers.CharField()
    additional_information = serializers.CharField()
    application_url = serializers.CharField()
    floor_plan_image = serializers.CharField()
    image_urls = serializers.ListField()
    url = serializers.CharField()
    title = serializers.CharField()
    site_owner = serializers.CharField()
    services = serializers.ListField()
    apartment_state_of_sale = serializers.CharField()
    apartment_published = serializers.BooleanField()


class ProjectDocumentSerializerBase(serializers.Serializer):
    id = serializers.IntegerField(source="project_id")
    uuid = serializers.UUIDField(source="project_uuid")
    ownership_type = serializers.CharField(source="project_ownership_type")
    housing_company = serializers.CharField(source="project_housing_company")
    holding_type = serializers.CharField(source="project_holding_type")
    street_address = serializers.CharField(source="project_street_address")
    postal_code = serializers.CharField(source="project_postal_code")
    city = serializers.CharField(source="project_city")
    district = serializers.CharField(source="project_district")
    realty_id = serializers.CharField(source="project_realty_id")
    construction_year = serializers.IntegerField(source="project_construction_year")
    new_development_status = serializers.CharField(
        source="project_new_development_status"
    )
    new_housing = serializers.BooleanField(source="project_new_housing")
    apartment_count = serializers.IntegerField(source="project_apartment_count")
    parkingplace_count = serializers.IntegerField(source="project_parkingplace_count")
    state_of_sale = serializers.CharField(source="project_state_of_sale")
    has_elevator = serializers.BooleanField(source="project_has_elevator")
    has_sauna = serializers.BooleanField(source="project_has_sauna")
    construction_materials = serializers.ListField(
        source="project_construction_materials"
    )
    roof_material = serializers.CharField(source="project_roof_material")
    heating_options = serializers.ListField(source="project_heating_options")
    energy_class = serializers.CharField(source="project_energy_class")
    site_area = serializers.IntegerField(source="project_site_area")
    site_renter = serializers.CharField(source="project_site_renter")
    sanitation = serializers.CharField(source="project_sanitation")
    zoning_info = serializers.CharField(source="project_zoning_info")
    zoning_status = serializers.CharField(source="project_zoning_status")
    building_type = serializers.CharField(source="project_building_type")
    description = serializers.CharField(source="project_description")
    accessibility = serializers.CharField(source="project_accessibility")
    smoke_free = serializers.CharField(source="project_smoke_free")
    publication_start_time = serializers.DateTimeField(
        source="project_publication_start_time"
    )
    publication_end_time = serializers.DateTimeField(
        source="project_publication_end_time"
    )
    premarketing_start_time = serializers.DateTimeField(
        source="project_premarketing_start_time"
    )
    premarketing_end_time = serializers.DateTimeField(
        source="project_premarketing_end_time"
    )
    application_start_time = serializers.DateTimeField(
        source="project_application_start_time"
    )
    application_end_time = serializers.DateTimeField(
        source="project_application_end_time"
    )
    material_choice_dl = serializers.CharField(source="project_material_choice_dl")
    shareholder_meeting_date = serializers.DateTimeField(
        source="project_shareholder_meeting_date"
    )
    estimated_completion = serializers.CharField(source="project_estimated_completion")
    estimated_completion_date = serializers.DateTimeField(
        source="project_estimated_completion_date"
    )
    completion_date = serializers.DateTimeField(source="project_completion_date")
    possession_transfer_date = serializers.DateTimeField(
        source="project_possession_transfer_date"
    )
    attachment_urls = serializers.ListField(source="project_attachment_urls")
    main_image_url = serializers.CharField(source="project_main_image_url")
    image_urls = serializers.ListField(source="project_image_urls")
    virtual_presentation_url = serializers.CharField(
        source="project_virtual_presentation_url"
    )
    acc_salesperson = serializers.CharField(source="project_acc_salesperson")
    acc_financeofficer = serializers.CharField(source="project_acc_financeofficer")
    project_manager = serializers.CharField(source="project_project_manager")
    constructor = serializers.CharField(source="project_constructor")
    housing_manager = serializers.CharField(source="project_housing_manager")
    estate_agent = serializers.CharField(source="project_estate_agent")
    estate_agent_email = serializers.CharField(source="project_estate_agent_email")
    estate_agent_phone = serializers.CharField(source="project_estate_agent_phone")
    coordinate_lat = serializers.FloatField(source="project_coordinate_lat")
    coordinate_lon = serializers.FloatField(source="project_coordinate_lon")
    url = serializers.CharField(source="project_url")
    barred_bank_account = serializers.CharField(source="project_barred_bank_account")
    regular_bank_account = serializers.CharField(source="project_regular_bank_account")
    published = serializers.BooleanField(source="project_published")
    archived = serializers.BooleanField(source="project_archived")


class ProjectDocumentListSerializer(ProjectDocumentSerializerBase):
    pass


class ProjectDocumentDetailSerializer(ProjectDocumentSerializerBase):
    installment_templates = serializers.SerializerMethodField()
    apartments = serializers.SerializerMethodField()
    extra_data = serializers.SerializerMethodField()
    lottery_completed_at = serializers.SerializerMethodField()
    application_count = serializers.SerializerMethodField()

    def get_installment_templates(self, obj):
        installment_templates = ProjectInstallmentTemplate.objects.filter(
            project_uuid=obj["project_uuid"]
        )
        return ProjectInstallmentTemplateSerializer(
            installment_templates, many=True
        ).data

    def get_apartments(self, obj):
        all_reservations = ApartmentReservation.objects.filter(
            apartment_uuid__in=self.apartment_uuids
        ).active()

        reservation_counts = (
            ApartmentReservation.objects.active()
            .values("apartment_uuid")
            .annotate(reservation_count=Count("apartment_uuid"))
        )

        customer_other_winning_apartments = (
            ApartmentReservation.objects.reserved()
            .exclude(pk=OuterRef("pk"))
            .filter(
                apartment_uuid__in=self.apartment_uuids,
                customer=OuterRef("customer__pk"),
            )
        )
        winning_reservations = (
            all_reservations.related_fields()
            .active()
            .filter(queue_position=1)
            .annotate(
                customer_has_other_winning_apartments=Exists(
                    customer_other_winning_apartments
                )
            )
            # Winning reservations are sorted by list_position so that the results will
            # be consistent even if there are multiple winning reservations for the same
            # apartment. That should not normally happen.
            .order_by("list_position")
        )

        return ApartmentSerializer(
            self.apartment_objs,
            many=True,
            context={
                "project_uuid": obj.project_uuid,
                "reservation_counts": reservation_counts,
                "winning_reservations": winning_reservations,
                "reserved_reservations": ApartmentReservation.objects.filter(
                    apartment_uuid__in=self.apartment_uuids
                ).reserved(),
                "reservations": all_reservations,
            },
        ).data

    def get_extra_data(self, obj):
        try:
            extra_data = ProjectExtraData.objects.get(project_uuid=obj.project_uuid)
        except ProjectExtraData.DoesNotExist:
            extra_data = ProjectExtraData()
        return ProjectExtraDataSerializer(extra_data).data

    def get_lottery_completed_at(self, obj) -> datetime:
        lottery_completed_at = LotteryEvent.objects.filter(
            apartment_uuid__in=self.apartment_uuids
        ).aggregate(Max("timestamp"))["timestamp__max"]
        return lottery_completed_at

    def get_application_count(self, obj) -> int:
        return (
            Application.objects.filter(
                application_apartments__apartment_uuid__in=self.apartment_uuids
            )
            # this is needed so that decryption won't be used, which would slow this
            # query down substantially
            .only("id")
            .distinct()
            .count()
        )

    @cached_property
    def apartment_objs(self):
        return get_apartments(self.instance.project_uuid)

    @cached_property
    def apartment_uuids(self):
        return [a.uuid for a in self.apartment_objs]
