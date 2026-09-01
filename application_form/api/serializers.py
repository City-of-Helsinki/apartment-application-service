import logging
from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from enumfields.drf import EnumField, EnumSupportSerializerMixin
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import IntegerField, UUIDField

from apartment.elastic.queries import (
    get_apartment,
    get_apartment_project_uuid,
    get_apartment_uuids,
    get_project,
)
from apartment.enums import OwnershipType
from apartment_application_service.settings import (
    METADATA_HANDLER_INFORMATION,
    METADATA_HASO_PROCESS_NUMBER,
    METADATA_HITAS_PROCESS_NUMBER,
)
from application_form import error_codes
from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
    ApplicationArrivalMethod,
    ApplicationType,
    OfferState,
)
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
    Applicant,
    Application,
    Offer,
)
from application_form.services.application import (
    cancel_reservations_replaced_by_late_application,
    create_application,
    get_sold_apartment_uuids,
    send_sales_notification_email,
)
from application_form.services.constants import COMMITTED_RESERVATION_STATES
from application_form.services.offer import update_offer
from application_form.validators import ProjectApplicantValidator, SSNSuffixValidator
from connections.enums import ApartmentStateOfSale
from customer.models import Customer

_logger = logging.getLogger(__name__)


User = get_user_model()


class ApplicantSerializerBase(serializers.ModelSerializer):
    class Meta:
        model = Applicant
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "street_address",
            "city",
            "postal_code",
            "age",
        ]
        extra_kwargs = {"age": {"read_only": True}}


class ApplicantSerializer(ApplicantSerializerBase):
    date_of_birth = serializers.DateField(write_only=True)

    class Meta(ApplicantSerializerBase.Meta):
        fields = ApplicantSerializerBase.Meta.fields + ["date_of_birth", "ssn_suffix"]

    def validate(self, attrs):
        super().validate(attrs)
        date_of_birth = attrs.get("date_of_birth")
        validator = SSNSuffixValidator(date_of_birth)
        try:
            validator(attrs.get("ssn_suffix", ""))
        except ValidationError as e:
            message = f"Invalid SSN suffix for applicant was received: {e.args[0]}"
            _logger.warning(message)
            raise ValidationError(
                detail={"ssn_suffix": message},
                code=error_codes.E1000_SSN_SUFFIX_IS_NOT_VALID,
            )
        return attrs

    def __init__(self, *args, **kwargs):
        exclude_fields = kwargs.pop("exclude_fields", None)
        super().__init__(*args, **kwargs)
        if exclude_fields:
            for field_name in exclude_fields:
                self.fields.pop(field_name, None)


class ApplicationApartmentSerializer(serializers.Serializer):
    priority = IntegerField(min_value=0, max_value=5)
    identifier = UUIDField()


class ApplicationSerializerBase(serializers.ModelSerializer):
    application_uuid = UUIDField(source="external_uuid")
    application_type = EnumField(ApplicationType, source="type", write_only=True)
    project_id = UUIDField(write_only=True)
    apartments = ApplicationApartmentSerializer(write_only=True, many=True)

    class Meta:
        model = Application
        fields = (
            "application_uuid",
            "application_type",
            "has_children",
            "additional_applicant",
            "right_of_residence",
            "right_of_residence_is_old_batch",
            "project_id",
            "apartments",
            "has_hitas_ownership",
            "is_right_of_occupancy_housing_changer",
            "drupal_application_id",
        )
        extra_kwargs = {
            # We only support creating applications for now,
            # and only the application UUID will be returned
            # in the response.
            "has_children": {"write_only": True},
            "right_of_residence": {"write_only": True},
            "right_of_residence_is_old_batch": {"write_only": True},
            "project_id": {"write_only": True},
            "has_hitas_ownership": {"write_only": True},
            "is_right_of_occupancy_housing_changer": {"write_only": True},
            "drupal_application_id": {
                "write_only": True,
                "required": False,
                "allow_null": True,
            },
        }

    def _validate_hitas_post_period_reservation(
        self, project, validated_data, project_apartment_uuids, profile
    ):
        """
        Validate HITAS post-period reservation rules.

        Parameters:
            project: Elastic project document for the application.
            validated_data (dict): Validated application payload.
            project_apartment_uuids (list): Apartment UUIDs in the project.
            profile: Primary profile of the applying customer.

        Raises:
            ValidationError: When HITAS late-reservation rules are violated.
        """
        if len(validated_data.get("apartments", [])) != 1:
            raise serializers.ValidationError(
                {
                    "detail": _(
                        "HITAS post-period reservation must contain "
                        "exactly one apartment"
                    )
                },
                code=400,
            )

        target_uuid = validated_data["apartments"][0]["identifier"]
        try:
            target_apartment = get_apartment(target_uuid, include_project_fields=True)
        except ObjectDoesNotExist:
            raise serializers.ValidationError(
                {"detail": _("Apartment not found")},
                code=400,
            )

        allowed_states = {ApartmentStateOfSale.FREE_FOR_RESERVATIONS.value}
        state_of_sale = target_apartment.apartment_state_of_sale
        if not state_of_sale or state_of_sale.upper() not in allowed_states:
            raise serializers.ValidationError(
                {"detail": _("Cannot reserve an apartment that is not free")},
                code=400,
            )

        existing_reservations = (
            ApartmentReservation.objects.select_for_update()
            .active()
            .filter(
                apartment_uuid__in=project_apartment_uuids,
                customer__primary_profile=profile,
            )
        )
        if existing_reservations.exists():
            raise serializers.ValidationError(
                {"detail": _("Customer already has a reservation in this project")},
                code=400,
            )

    def _validate_no_blocking_reservations(self, profile, project_apartment_uuids):
        """
        Reject create when the customer is already committed to an apartment.

        Parameters:
            profile: Primary profile of the applying customer.
            project_apartment_uuids (list): Apartment UUIDs in the project.

        Raises:
            ValidationError: When a blocking reservation exists.
        """
        reservations_in_project = ApartmentReservation.objects.filter(
            application_apartment__application__customer__primary_profile__id=profile.id,  # noqa: E501
            apartment_uuid__in=project_apartment_uuids,
            state__in=COMMITTED_RESERVATION_STATES,
        )
        if reservations_in_project.exists():
            raise serializers.ValidationError(
                {
                    "detail": _(
                        "User already has offered or sold apartment in this project"
                    )
                },
                code=400,
            )

    def _schedule_sales_notification_email(self, application, project, validated_data):
        """
        Schedule salesperson email after the surrounding transaction commits.

        Parameters:
            application: Created application instance.
            project: Elastic project document.
            validated_data (dict): Validated application payload.
        """
        apartment_uuids = [
            apt["identifier"] for apt in validated_data.get("apartments")
        ]

        def _send_sales_notification():
            try:
                send_sales_notification_email(
                    application,
                    project,
                    application_apartment_uuids=apartment_uuids,
                )
            except Exception:
                _logger.exception(
                    "Failed to send sales notification email for application %s",
                    application.pk,
                )

        transaction.on_commit(_send_sales_notification)

    def create(self, validated_data):
        """
        Create an application, including HASO/HITAS late-application handling.

        Parameters:
            validated_data (dict): Validated application payload.

        Returns:
            Application: The created application instance.
        """
        submitted_late_override = validated_data.pop("submitted_late", None)
        validated_data = self.prepare_metadata(validated_data)

        project = get_project(
            get_apartment_project_uuid(
                validated_data.get("apartments")[0]["identifier"]
            ).project_uuid
        )

        is_submitted_late = False
        if project.project_application_end_time:
            is_submitted_late = (
                datetime.now().replace(tzinfo=timezone.get_default_timezone())
                > project.project_application_end_time
            )
        if submitted_late_override is not None:
            is_submitted_late = submitted_late_override

        is_haso = project.project_ownership_type.lower() == OwnershipType.HASO.value
        is_hitas = project.project_ownership_type.lower() == OwnershipType.HITAS.value
        project_apartment_uuids = get_apartment_uuids(project.project_uuid)
        profile = validated_data.get("profile") or self.context["request"].user.profile

        self._validate_no_blocking_reservations(profile, project_apartment_uuids)

        target_apartment_uuids = [
            apartment["identifier"]
            for apartment in validated_data.get("apartments", [])
        ]
        if (
            not settings.ALLOW_APPLICATIONS_TO_SOLD_APARTMENTS
            and get_sold_apartment_uuids(target_apartment_uuids)
        ):
            raise serializers.ValidationError(
                {"detail": _("Cannot apply to a sold apartment")},
                code=400,
            )

        if is_submitted_late and not (
            project.project_can_apply_afterwards and (is_haso or is_hitas)
        ):
            raise serializers.ValidationError(
                {"detail": _("Cannot submit late application to this apartment")},
                code=400,
            )

        with transaction.atomic():
            if is_submitted_late and is_hitas:
                self._validate_hitas_post_period_reservation(
                    project, validated_data, project_apartment_uuids, profile
                )

            application = create_application(
                validated_data,
                user=self.context.get("salesperson"),
                submitted_late=is_submitted_late,
            )

            if is_submitted_late and is_haso:
                cancel_reservations_replaced_by_late_application(
                    application, project_apartment_uuids, profile
                )

            if is_submitted_late and (is_haso or is_hitas):
                self._schedule_sales_notification_email(
                    application, project, validated_data
                )

        return application

    def prepare_metadata(self, validated_data):
        if validated_data.get("type", None) == ApplicationType.HASO:
            validated_data["process_number"] = METADATA_HASO_PROCESS_NUMBER
        else:
            validated_data["process_number"] = METADATA_HITAS_PROCESS_NUMBER
        validated_data["handler_information"] = METADATA_HANDLER_INFORMATION
        return validated_data


class ApplicationSerializer(ApplicationSerializerBase):
    applicant = ApplicantSerializer(write_only=True)
    additional_applicant = ApplicantSerializer(write_only=True, allow_null=True)
    project_id = UUIDField(write_only=True)

    class Meta(ApplicationSerializerBase.Meta):
        fields = ApplicationSerializerBase.Meta.fields + (
            "applicant",
            "additional_applicant",
        )

    def _get_senders_name_from_applicants_data(self, validated_data):
        additional_applicant = validated_data.get("additional_applicant")
        sender_names = validated_data["profile"].full_name
        if additional_applicant:
            additional_applicant_name = " ".join(
                [additional_applicant["first_name"], additional_applicant["last_name"]]
            )
            sender_names += "/ {}".format(additional_applicant_name)
        return sender_names

    def create(self, validated_data):
        validated_data["profile"] = self.context["request"].user.profile
        return super().create(validated_data)

    def prepare_metadata(self, validated_data):
        validated_data["sender_names"] = self._get_senders_name_from_applicants_data(
            validated_data
        )
        validated_data["method_of_arrival"] = (
            ApplicationArrivalMethod.ELECTRONICAL_SYSTEM
        )
        return super().prepare_metadata(validated_data)

    def validate_ssn_suffix(self, value):
        date_of_birth = self.context["request"].user.profile.date_of_birth
        validator = SSNSuffixValidator(date_of_birth)
        try:
            validator(value)
        except ValidationError as e:
            message = f"""Invalid SSN suffix for the primary applicant was
            received: {e.args[0]}"""
            _logger.warning(message)
            raise ValidationError(
                detail=message,
                code=error_codes.E1000_SSN_SUFFIX_IS_NOT_VALID,
            )
        return value

    def validate(self, attrs):
        project_uuid = attrs["project_id"]
        applicants = []
        applicant_data = attrs.get("applicant")
        if applicant_data:
            applicants.append(
                (applicant_data["date_of_birth"], applicant_data["ssn_suffix"])
            )

        additional_applicant = attrs.get("additional_applicant")
        if additional_applicant:
            applicants.append(
                (
                    additional_applicant["date_of_birth"],
                    additional_applicant["ssn_suffix"],
                )
            )
        validator = ProjectApplicantValidator()
        validator(project_uuid, applicants)

        return super().validate(attrs)


class ReservationOfferSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = Offer
        fields = (
            "id",
            "created_at",
            "valid_until",
            "state",
            "concluded_at",
            "comment",
            "is_expired",
        )


class CustomerOfferUpdateSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    state = EnumField(OfferState, required=True)

    class Meta:
        model = Offer
        fields = ("state",)

    def validate_state(self, value):
        if value not in (OfferState.ACCEPTED, OfferState.REJECTED):
            raise ValidationError("State must be accepted or rejected.")
        return value

    def validate(self, attrs):
        offer = self.instance
        if offer.state != OfferState.PENDING:
            raise ValidationError("Offer has already been concluded.")
        if offer.is_expired:
            raise ValidationError("Offer has expired.")
        return attrs

    def update(self, instance, validated_data):
        user = self.context["request"].user
        return update_offer(instance, validated_data, user=user)


class PendingOfferReminderProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.CharField()


class PendingOfferReminderCustomerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    primary_profile = PendingOfferReminderProfileSerializer()


class PendingOfferReminderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    valid_until = serializers.DateField()
    apartment_uuid = serializers.UUIDField()
    project_uuid = serializers.UUIDField()
    customer = PendingOfferReminderCustomerSerializer()


class ApartmentReservationSerializerBase(serializers.ModelSerializer):
    state = EnumField(ApartmentReservationState, read_only=True)
    lottery_position = IntegerField(
        source="application_apartment.lotteryeventresult.result_position",
        allow_null=True,
        read_only=True,
    )
    priority_number = serializers.IntegerField(
        source="application_apartment.priority_number", allow_null=True, read_only=True
    )
    offer = ReservationOfferSerializer(read_only=True)

    queue_position_before_cancelation = serializers.IntegerField(
        allow_null=True, required=False, read_only=True, default=None
    )

    class Meta:
        model = ApartmentReservation
        fields = (
            "id",
            "apartment_uuid",
            "lottery_position",
            "queue_position",
            "queue_position_before_cancelation",
            "priority_number",
            "state",
            "offer",
            "right_of_residence",
            "right_of_residence_is_old_batch",
            "has_children",
            "has_hitas_ownership",
            "is_age_over_55",
            "is_right_of_occupancy_housing_changer",
            "submitted_late",
        )
        read_only_fields = (
            "id",
            "lottery_position",
            "queue_position",
            "priority_number",
            "state",
            "right_of_residence",
            "right_of_residence_is_old_batch",
            "has_children",
            "has_hitas_ownership",
            "is_age_over_55",
            "is_right_of_occupancy_housing_changer",
            "submitted_late",
        )

        def to_representation(self, instance):
            data = super().to_representation(instance)
            if instance.queue_position_before_cancelation is None:
                data["queue_position_before_cancelation"] = None
            return data


# Cancellation reasons triggered automatically by the system (no human actor)
_SYSTEM_CANCELLATION_REASONS = {
    ApartmentReservationCancellationReason.LOWER_PRIORITY,
    ApartmentReservationCancellationReason.OTHER_APARTMENT_OFFERED,
}


class ApartmentReservationSerializer(ApartmentReservationSerializerBase):
    """
    Public serializer for apartment reservations, used by the Drupal-facing API.

    In addition to the base fields, this serializer provides:
    - state_change_events: full history of state transitions
    - cancellation_reason: raw enum value of the cancellation reason, or null
    - cancellation_actor: who initiated the cancellation
        "seller"  – manual action recorded by the seller (incl. registering offer
                    rejection on behalf of the customer)
        "system"  – automatic action by the system (lottery lower-priority removal,
                    other-apartment-offered cleanup)
        null      – reservation is not cancelled
    - cancellation_timestamp: ISO timestamp of the cancellation event, or null
    """

    state_change_events = serializers.SerializerMethodField()
    cancellation_reason = serializers.SerializerMethodField()
    cancellation_actor = serializers.SerializerMethodField()
    cancellation_timestamp = serializers.SerializerMethodField()

    class Meta(ApartmentReservationSerializerBase.Meta):
        fields = ApartmentReservationSerializerBase.Meta.fields + (
            "state_change_events",
            "cancellation_reason",
            "cancellation_actor",
            "cancellation_timestamp",
        )

    def _get_latest_canceled_event(self, obj):
        """Return the newest CANCELED state-change event, or None."""
        if obj.state != ApartmentReservationState.CANCELED:
            return None
        return (
            obj.state_change_events.filter(state=ApartmentReservationState.CANCELED)
            .order_by("-timestamp", "-id")
            .first()
        )

    def get_state_change_events(self, obj):
        return [
            {
                "timestamp": ev.timestamp,
                "state": ev.state.value,
                "cancellation_reason": (
                    ev.cancellation_reason.value if ev.cancellation_reason else None
                ),
            }
            for ev in obj.state_change_events.all()
        ]

    def get_cancellation_reason(self, obj):
        ev = self._get_latest_canceled_event(obj)
        if not ev or not ev.cancellation_reason:
            return None
        return ev.cancellation_reason.value

    def get_cancellation_actor(self, obj):
        """
        Returns who initiated the cancellation:
        - "system"  for automatic lottery/offer-pipeline actions
                    (lower_priority, other_apartment_offered)
        - "seller"  for all seller-recorded actions, including registering an
                    offer rejection (offer_rejected) on behalf of the customer
        - null      if the reservation is not cancelled
        """
        ev = self._get_latest_canceled_event(obj)
        if not ev:
            return None
        if ev.cancellation_reason in _SYSTEM_CANCELLATION_REASONS:
            return "system"
        return "seller"

    def get_cancellation_timestamp(self, obj):
        ev = self._get_latest_canceled_event(obj)
        return ev.timestamp if ev else None


class ApartmentReservationStateChangeEventUserSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="profile_or_user_first_name")
    last_name = serializers.CharField(source="profile_or_user_last_name")
    email = serializers.EmailField(source="profile_or_user_email")

    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email")


class ApartmentReservationStateChangeEventSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    changed_by = ApartmentReservationStateChangeEventUserSerializer(
        source="user", read_only=True
    )
    queue_position = serializers.IntegerField(
        required=False, allow_null=True, write_only=True
    )
    submitted_late = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = ApartmentReservationStateChangeEvent
        fields = (
            "timestamp",
            "state",
            "comment",
            "cancellation_reason",
            "changed_by",
            "queue_position",
            "submitted_late",
        )
        read_only_fields = (
            "timestamp",
            "changed_by",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["state"].choices.pop(ApartmentReservationState.CANCELED.value)


class ApartmentReservationCancelEventSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    new_customer_id = serializers.PrimaryKeyRelatedField(
        source="replaced_by.customer",
        queryset=Customer.objects.all(),
        required=False,
        help_text="Used only with cancellation reason `transferred`.",
    )
    new_reservation_id = serializers.PrimaryKeyRelatedField(
        source="replaced_by",
        required=False,
        read_only=True,
        help_text="Used only with cancellation reason `transferred`.",
    )

    class Meta:
        model = ApartmentReservationStateChangeEvent
        fields = (
            "timestamp",
            "state",
            "comment",
            "cancellation_reason",
            "new_customer_id",
            "new_reservation_id",
        )
        read_only_fields = ("timestamp", "state", "new_reservation_id")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cancellation_reason"].required = True
        self.fields["cancellation_reason"].allow_null = False
        self.fields["cancellation_reason"].allow_blank = False

    def validate_cancellation_reason(self, value):
        if value not in (
            ApartmentReservationCancellationReason.TERMINATED,
            ApartmentReservationCancellationReason.CANCELED,
            ApartmentReservationCancellationReason.RESERVATION_AGREEMENT_CANCELED,
            ApartmentReservationCancellationReason.TRANSFERRED,
        ):
            raise ValidationError(f"Illegal value {value}")
        return value

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        if (
            validated_data["cancellation_reason"]
            == ApartmentReservationCancellationReason.TRANSFERRED
        ):
            validated_data["customer"] = validated_data.pop("replaced_by", {}).pop(
                "customer", {}
            )
            if not validated_data["customer"]:
                raise ValidationError(
                    "new_customer_id is required when cancellation_reason is "
                    '"transferred".'
                )
        return validated_data

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if (
            instance.cancellation_reason
            != ApartmentReservationCancellationReason.TRANSFERRED
        ):
            ret.pop("new_customer_id", None)
            ret.pop("new_reservation_id", None)
        return ret


class OfferMessageQueryParamsSerializer(serializers.Serializer):
    valid_until = serializers.DateField(required=False)


class QueuePreviewInputSerializer(serializers.Serializer):
    reservation_id = serializers.IntegerField(required=False)
    customer_id = serializers.IntegerField(required=False)
    queue_position = serializers.IntegerField(required=False, min_value=1)
    submitted_late = serializers.BooleanField(required=False)
    state = serializers.ChoiceField(
        required=False,
        choices=[state.value for state in ApartmentReservationState],
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        has_reservation_id = attrs.get("reservation_id") is not None
        has_customer_id = attrs.get("customer_id") is not None

        if has_reservation_id == has_customer_id:
            raise ValidationError(
                "Exactly one of reservation_id or customer_id must be provided."
            )
        return attrs


class QueuePreviewProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(allow_null=True)
    last_name = serializers.CharField(allow_null=True)
    email = serializers.CharField(allow_null=True)


class QueuePreviewCustomerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    primary_profile = QueuePreviewProfileSerializer(allow_null=True)
    secondary_profile = QueuePreviewProfileSerializer(allow_null=True)


class QueuePreviewReservationSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    queue_position = serializers.IntegerField(allow_null=True)
    state = serializers.SerializerMethodField()
    submitted_late = serializers.BooleanField()
    customer = QueuePreviewCustomerSerializer()

    def get_state(self, obj):
        return obj.state.value if hasattr(obj.state, "value") else obj.state
