from rest_framework import exceptions
from rest_framework.views import exception_handler


def drf_exception_handler(exc, context):
    """
    Returns full details from APIException.
    """
    response = exception_handler(exc, context)

    if response is not None and isinstance(exc, exceptions.APIException):
        response.data = exc.get_full_details()

    return response
