"""
Serializers for W-2 API
"""
from rest_framework import serializers


class W2UploadSerializer(serializers.Serializer):
    """Validates W-2 PDF uploads"""
    
    file = serializers.FileField(required=True)

    def validate_file(self, value):
        # check size (10MB max)
        max_size = 10 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File size ({value.size / 1024 / 1024:.2f}MB) exceeds max ({max_size / 1024 / 1024}MB)."
            )

        # check extension
        if not value.name.lower().endswith(".pdf"):
            raise serializers.ValidationError(
                f"Only PDF files are accepted. Got: {value.name.split('.')[-1]}"
            )

        # check content type (if provided)
        content_type = getattr(value, "content_type", "")
        if content_type and content_type not in ["application/pdf", "application/x-pdf"]:
            raise serializers.ValidationError(f"Invalid content type: {content_type}")

        # check PDF magic bytes
        value.seek(0)
        header = value.read(8)
        value.seek(0)

        if not header.startswith(b"%PDF"):
            raise serializers.ValidationError(
                "File doesn't appear to be a valid PDF (missing %PDF header)."
            )

        return value


class W2ExtractedDataSerializer(serializers.Serializer):
    """Extracted W-2 data"""
    ein = serializers.CharField()
    ssn = serializers.CharField()
    wages = serializers.DecimalField(max_digits=12, decimal_places=2)
    federal_tax_withheld = serializers.DecimalField(max_digits=12, decimal_places=2)
