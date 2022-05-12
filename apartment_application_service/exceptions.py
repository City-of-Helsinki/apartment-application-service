from django.core.exceptions import ValidationError
from rest_framework import exceptions
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.fields import get_error_detail
from rest_framework.views import exception_handler


def drf_exception_handler(exc, context):
    """
    Returns full details from APIException.
    """

    # convert Django ValidationError to DRF ValidationError
    if isinstance(exc, ValidationError):
        return exception_handler(
            DRFValidationError(detail=get_error_detail(exc)), context
        )

    response = exception_handler(exc, context)

    if response is not None and isinstance(exc, exceptions.APIException):
        response.data = exc.get_full_details()

    return response
