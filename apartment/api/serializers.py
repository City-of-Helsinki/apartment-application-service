from rest_framework import serializers


class ProjectDocumentSerializer(serializers.Serializer):
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
