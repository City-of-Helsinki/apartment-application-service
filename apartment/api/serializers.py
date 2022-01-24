from rest_framework import serializers

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
    site_owner = serializers.CharField(source="project_site_owner")
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
    posession_transfer_date = serializers.DateTimeField(
        source="project_posession_transfer_date"
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


class ProjectDocumentListSerializer(ProjectDocumentSerializerBase):
    pass


class ProjectDocumentDetailSerializer(ProjectDocumentSerializerBase):
    installment_templates = serializers.SerializerMethodField()

    def get_installment_templates(self, obj):
        installment_templates = ProjectInstallmentTemplate.objects.filter(
            project_uuid=obj["project_uuid"]
        )
        return ProjectInstallmentTemplateSerializer(
            installment_templates, many=True
        ).data
