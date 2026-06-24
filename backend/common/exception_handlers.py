"""Custom DRF exception handling.

Translates Django's ``django.core.exceptions.ValidationError`` (raised from
model ``full_clean()``/``clean()`` during ``save()``) into a 400 response that
matches the API's ``{"error": True, "errors": ...}`` convention. Without this,
such errors propagate as HTTP 500.
"""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, DjangoValidationError):
        errors = getattr(exc, "message_dict", None) or exc.messages
        return Response(
            {"error": True, "errors": errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Unhandled exception: log it and return None so Django produces its
    # standard 500 response.
    logger.exception("Unhandled exception in API view", exc_info=exc)
    return None
