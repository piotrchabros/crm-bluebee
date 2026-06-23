"""Custom DRF exception handling.

Translates Django's ``django.core.exceptions.ValidationError`` (raised from
model ``full_clean()``/``clean()`` during ``save()``) into a 400 response that
matches the API's ``{"error": True, "errors": ...}`` convention. Without this,
such errors propagate as HTTP 500.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            errors = exc.message_dict
        else:
            errors = exc.messages
        return Response(
            {"error": True, "errors": errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return response
