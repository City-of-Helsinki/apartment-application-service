from django.utils import translation

from application_form.api.sales.views import _apply_manual_change_comments
from application_form.enums import ApartmentReservationState


def test_apply_manual_change_comments_use_finnish_always():
    """
    Should always use the Finnish language ("fi") translation in the persisted\
    auto-generated manual change comments no matter what the active language is.
    """
    validated_data = {}

    with translation.override("en"):
        _apply_manual_change_comments(
            validated_data=validated_data,
            queue_position=3,
            new_state=ApartmentReservationState.OFFERED,
            old_queue_position=1,
            submitted_late_changed=True,
            old_submitted_late=False,
            new_submitted_late=True,
        )

    comment = validated_data["comment"]
    assert "Jonosija muuttui sijasta 1. sijaan 3." in comment
    assert "Asetettu jälkihakemukseksi" in comment

