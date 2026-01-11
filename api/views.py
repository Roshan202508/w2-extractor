"""
W-2 Processing API Views
"""
import logging

from asgiref.sync import async_to_sync
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from rest_framework import status, serializers
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import InvalidFileException
from .serializers import W2UploadSerializer
from .services import ThirdPartyAPIClient, W2DataExtractor

logger = logging.getLogger(__name__)


# Response serializers for Swagger documentation
class HealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()
    version = serializers.CharField()


class ExtractedDataSerializer(serializers.Serializer):
    ein = serializers.CharField()
    ssn = serializers.CharField()
    wages = serializers.CharField()
    federal_tax_withheld = serializers.CharField()


class W2SuccessDataSerializer(serializers.Serializer):
    report_id = serializers.CharField()
    file_id = serializers.CharField()


class W2SuccessResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = W2SuccessDataSerializer()
    extracted_data = ExtractedDataSerializer()


class ErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    error = ErrorDetailSerializer()


class HealthCheckView(APIView):
    """Health check endpoint"""

    @extend_schema(
        summary="Health Check",
        description="Returns service health status. Use for load balancer probes.",
        responses={200: HealthResponseSerializer},
        tags=["Health"],
    )
    def get(self, request):
        return Response({
            "status": "healthy",
            "service": "w2-extractor",
            "version": "1.0.0",
        })


class W2ProcessView(APIView):
    """
    Endpoint for processing W-2 PDFs.
    
    The view method is sync (DRF limitation), but internal processing
    is async via async_to_sync wrapper.
    """
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Process W-2 PDF",
        description="""
Upload a W-2 PDF file to extract tax data and report to third-party API.

**Flow:**
1. Validate uploaded PDF file
2. Extract W-2 data (EIN, SSN, Wages, Federal Tax Withheld)
3. Submit extracted data to third-party API
4. Upload original PDF to third-party API
5. Return success response with IDs

**File Requirements:**
- Format: PDF only
- Max size: 10MB
- Must be text-based (not scanned image)
        """,
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "format": "binary",
                        "description": "W-2 PDF file to process",
                    }
                },
                "required": ["file"],
            }
        },
        responses={
            200: W2SuccessResponseSerializer,
            400: ErrorResponseSerializer,
            422: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Success Response",
                value={
                    "success": True,
                    "message": "W-2 processed successfully",
                    "data": {
                        "report_id": "550e8400-e29b-41d4-a716-446655440000",
                        "file_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                    },
                    "extracted_data": {
                        "ein": "12-3456789",
                        "ssn": "123-45-6789",
                        "wages": "75000.00",
                        "federal_tax_withheld": "12500.00",
                    },
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Invalid File Error",
                value={
                    "success": False,
                    "error": {
                        "code": "invalid_file",
                        "message": "Only PDF files are accepted.",
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
        tags=["W-2 Processing"],
    )
    def post(self, request):
        """Process W-2 PDF file"""
        logger.info("Processing W-2 upload request")

        # validate the file
        serializer = W2UploadSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Validation failed: {serializer.errors}")
            raise InvalidFileException(
                detail=self._format_errors(serializer.errors),
                code="file_validation_failed",
            )

        uploaded_file = serializer.validated_data["file"]
        filename = uploaded_file.name
        logger.info(f"Processing: {filename} ({uploaded_file.size} bytes)")

        # read file content
        file_content = uploaded_file.read()

        # async processing wrapped for DRF compatibility
        result = async_to_sync(self._process_async)(file_content, filename)

        return Response({
            "success": True,
            "message": "W-2 processed successfully",
            "data": {
                "report_id": result["report_id"],
                "file_id": result["file_id"],
            },
            "extracted_data": result["extracted_data"],
        })

    async def _process_async(self, file_content, filename):
        """Async processing logic."""
        # extract data from PDF
        extractor = W2DataExtractor()
        extracted = await extractor.extract(file_content)
        
        # mask sensitive data in logs
        logger.info(f"Extracted - EIN: **-***{extracted.ein[-4:]}, SSN: ***-**-{extracted.ssn[-4:]}")

        # send to third-party API (async HTTP calls)
        async with ThirdPartyAPIClient() as client:
            report_id = await client.submit_report(extracted.to_dict())
            logger.info(f"Report created: {report_id}")

            file_id = await client.upload_file(report_id, file_content, filename)
            logger.info(f"File uploaded: {file_id}")

        return {
            "report_id": report_id,
            "file_id": file_id,
            "extracted_data": extracted.to_dict(),
        }

    def _format_errors(self, errors):
        """Flatten validation errors into a string"""
        msgs = []
        for field, errs in errors.items():
            if isinstance(errs, list):
                msgs.extend(str(e) for e in errs)
            else:
                msgs.append(str(errs))
        return "; ".join(msgs)
