"""
W-2 Processing API Views
"""
import logging

from asgiref.sync import async_to_sync
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import InvalidFileException
from .serializers import W2UploadSerializer
from .services import ThirdPartyAPIClient, W2DataExtractor

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """Health check - returns 200 if service is up"""

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

    def post(self, request):
        """
        Process W-2 PDF.
        
        Flow:
        1. Validate uploaded file
        2. Extract W-2 data (EIN, SSN, wages, tax)
        3. POST to /reports -> get report_id
        4. POST to /files with report_id -> get file_id
        5. Return success response
        """
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
        """
        Async processing logic.
        
        This runs in an async context even though the view is sync.
        """
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
