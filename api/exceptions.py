"""
Custom exceptions for W-2 processing
"""
import logging
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class W2ProcessingException(APIException):
    """Base exception for W-2 processing errors"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An error occurred while processing the W-2 form."
    default_code = "w2_processing_error"

    def __init__(self, detail=None, code=None, field=None):
        super().__init__(detail=detail, code=code)
        self.field = field


class InvalidFileException(W2ProcessingException):
    """Uploaded file is invalid or not a PDF"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The uploaded file is invalid."
    default_code = "invalid_file"


class PDFParsingException(W2ProcessingException):
    """Failed to parse PDF"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Failed to parse the PDF file."
    default_code = "pdf_parsing_error"


class DataExtractionException(W2ProcessingException):
    """Couldn't extract required fields from W-2"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Failed to extract required data from the W-2 form."
    default_code = "data_extraction_error"


class ThirdPartyAPIException(W2ProcessingException):
    """Third-party API call failed"""
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Failed to communicate with the third-party service."
    default_code = "third_party_api_error"


class ThirdPartyAuthenticationException(ThirdPartyAPIException):
    """Auth failed with third-party API"""
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Authentication with the third-party service failed."
    default_code = "third_party_auth_error"


class ThirdPartyTimeoutException(ThirdPartyAPIException):
    """Third-party API timed out"""
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    default_detail = "The third-party service timed out."
    default_code = "third_party_timeout"


def custom_exception_handler(exc, context):
    """
    Custom handler to ensure consistent error response format.
    
    All errors return:
    {
        "success": false,
        "error": {"code": "...", "message": "..."}
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_response = {
            "success": False,
            "error": {
                "code": getattr(exc, "default_code", "error"),
                "message": str(exc.detail) if hasattr(exc, "detail") else str(exc),
            },
        }

        # include field info if available
        if hasattr(exc, "field") and exc.field:
            error_response["error"]["details"] = {"field": exc.field}

        logger.error(f"API Error: {error_response['error']['code']} - {error_response['error']['message']}")
        response.data = error_response

    return response
