"""
Mock third-party API

Simulates the external W-2 reporting service for dev/testing.

Auth: X-API-Key: FinPro-Secret-Key
POST /reports -> {"report_id": "..."}
POST /files -> {"file_id": "..."}
"""
import logging
import uuid

from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

API_KEY = "FinPro-Secret-Key"

# in-memory storage (good enough for mock)
_reports = {}
_files = {}


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
