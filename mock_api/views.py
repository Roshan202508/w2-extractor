"""
Mock third-party API

Simulates the external W-2 reporting service for dev/testing.

Auth: X-API-Key: FinPro-Secret-Key
POST /reports -> {"report_id": "..."}
POST /files -> {"file_id": "..."}
"""
import logging
import uuid

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from rest_framework import status, serializers
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

API_KEY = "FinPro-Secret-Key"

# in-memory storage (good enough for mock)
_reports = {}
_files = {}


# Serializers for Swagger documentation
class ReportRequestSerializer(serializers.Serializer):
    ein = serializers.CharField(help_text="Employer Identification Number (XX-XXXXXXX)")
    ssn = serializers.CharField(help_text="Social Security Number (XXX-XX-XXXX)")
    wages = serializers.CharField(help_text="Box 1 - Wages, tips, other compensation")
    federal_tax_withheld = serializers.CharField(help_text="Box 2 - Federal income tax withheld")


class ReportResponseSerializer(serializers.Serializer):
    report_id = serializers.CharField()


class FileResponseSerializer(serializers.Serializer):
    file_id = serializers.CharField()


class MockErrorSerializer(serializers.Serializer):
    error = serializers.CharField()


class MockAPIAuthMixin:
    """Check X-API-Key header"""

    def check_auth(self, request):
        key = request.headers.get("X-API-Key")
        if not key:
            return Response({"error": "Missing X-API-Key"}, status=status.HTTP_401_UNAUTHORIZED)
        if key != API_KEY:
            return Response({"error": "Invalid API key"}, status=status.HTTP_401_UNAUTHORIZED)
        return None


class MockReportView(MockAPIAuthMixin, APIView):
    """POST /reports - submit W-2 data"""
    parser_classes = [JSONParser]

    @extend_schema(
        summary="Submit W-2 Report",
        description="""
Submit extracted W-2 data to create a report.

**Authentication:** Requires `X-API-Key: FinPro-Secret-Key` header.

Returns a unique `report_id` to be used when uploading the PDF file.
        """,
        request=ReportRequestSerializer,
        responses={
            201: ReportResponseSerializer,
            400: MockErrorSerializer,
            401: MockErrorSerializer,
        },
        parameters=[
            OpenApiParameter(
                name="X-API-Key",
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
                description="API authentication key",
                examples=[
                    OpenApiExample("Valid Key", value="FinPro-Secret-Key"),
                ],
            ),
        ],
        examples=[
            OpenApiExample(
                "Valid Request",
                value={
                    "ein": "12-3456789",
                    "ssn": "123-45-6789",
                    "wages": "75000.00",
                    "federal_tax_withheld": "12500.00",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success Response",
                value={"report_id": "550e8400-e29b-41d4-a716-446655440000"},
                response_only=True,
                status_codes=["201"],
            ),
        ],
        tags=["Mock API"],
    )
    def post(self, request):
        auth_err = self.check_auth(request)
        if auth_err:
            return auth_err

        data = request.data
        required = ["ein", "ssn", "wages", "federal_tax_withheld"]
        missing = [f for f in required if f not in data]

        if missing:
            return Response(
                {"error": f"Missing fields: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        report_id = str(uuid.uuid4())
        _reports[report_id] = {"data": data}

        logger.info(f"Mock: created report {report_id}")
        return Response({"report_id": report_id}, status=status.HTTP_201_CREATED)


class MockFileUploadView(MockAPIAuthMixin, APIView):
    """POST /files - upload PDF"""
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Upload W-2 PDF File",
        description="""
Upload the original W-2 PDF file associated with a report.

**Authentication:** Requires `X-API-Key: FinPro-Secret-Key` header.

**Prerequisites:** Must first create a report via POST /reports to get a `report_id`.
        """,
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "report_id": {
                        "type": "string",
                        "description": "Report ID from POST /reports",
                    },
                    "file": {
                        "type": "string",
                        "format": "binary",
                        "description": "W-2 PDF file",
                    },
                },
                "required": ["report_id", "file"],
            }
        },
        responses={
            201: FileResponseSerializer,
            400: MockErrorSerializer,
            401: MockErrorSerializer,
        },
        parameters=[
            OpenApiParameter(
                name="X-API-Key",
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
                description="API authentication key",
                examples=[
                    OpenApiExample("Valid Key", value="FinPro-Secret-Key"),
                ],
            ),
        ],
        examples=[
            OpenApiExample(
                "Success Response",
                value={"file_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7"},
                response_only=True,
                status_codes=["201"],
            ),
        ],
        tags=["Mock API"],
    )
    def post(self, request):
        auth_err = self.check_auth(request)
        if auth_err:
            return auth_err

        report_id = request.data.get("report_id")
        if not report_id:
            return Response({"error": "Missing report_id"}, status=status.HTTP_400_BAD_REQUEST)

        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"error": "Missing file"}, status=status.HTTP_400_BAD_REQUEST)

        file_id = str(uuid.uuid4())
        _files[file_id] = {
            "report_id": report_id,
            "filename": uploaded.name,
            "size": uploaded.size,
        }

        logger.info(f"Mock: uploaded file {file_id} for report {report_id}")
        return Response({"file_id": file_id}, status=status.HTTP_201_CREATED)


# test utilities
def get_report(report_id):
    return _reports.get(report_id)

def get_file(file_id):
    return _files.get(file_id)

def clear_storage():
    _reports.clear()
    _files.clear()
