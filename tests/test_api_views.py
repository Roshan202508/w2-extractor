"""Tests for API views"""
import io
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal

from rest_framework.test import APIClient
from api.services.pdf_extractor import W2ExtractedData


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def auth_headers():
    return {"HTTP_X_API_KEY": "FinPro-Secret-Key"}


class TestHealthCheck:

    @pytest.mark.django_db
    def test_returns_healthy(self, client):
        resp = client.get("/api/health/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


class TestW2ProcessView:

    @pytest.mark.django_db
    def test_missing_file(self, client):
        resp = client.post("/api/w2/process/")
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    @pytest.mark.django_db
    def test_wrong_file_type(self, client):
        f = io.BytesIO(b"not a pdf")
        f.name = "test.txt"
        resp = client.post("/api/w2/process/", {"file": f})
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_file_too_large(self, client):
        # 11MB file
        content = b"%PDF-1.4\n" + b"x" * (11 * 1024 * 1024)
        f = io.BytesIO(content)
        f.name = "big.pdf"
        resp = client.post("/api/w2/process/", {"file": f})
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_fake_pdf(self, client):
        # .pdf extension but not actually a PDF
        f = io.BytesIO(b"not pdf content")
        f.name = "fake.pdf"
        resp = client.post("/api/w2/process/", {"file": f})
        assert resp.status_code == 400

    @pytest.mark.django_db
    @patch("api.views.ThirdPartyAPIClient")
    @patch("api.views.W2DataExtractor")
    def test_success(self, mock_extractor_cls, mock_client_cls, client, sample_w2_pdf_content):
        # mock extractor
        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=W2ExtractedData(
            ein="12-3456789",
            ssn="123-45-6789",
            wages=Decimal("75000"),
            federal_tax_withheld=Decimal("12500"),
        ))
        mock_extractor_cls.return_value = mock_extractor

        # mock client
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.submit_report = AsyncMock(return_value="report-123")
        mock_client.upload_file = AsyncMock(return_value="file-456")
        mock_client_cls.return_value = mock_client

        f = io.BytesIO(sample_w2_pdf_content)
        f.name = "w2.pdf"

        resp = client.post("/api/w2/process/", {"file": f})

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["report_id"] == "report-123"
        assert data["data"]["file_id"] == "file-456"


class TestMockAPI:

    @pytest.mark.django_db
    def test_reports_no_auth(self, client):
        resp = client.post("/mock-api/reports", {"ein": "12-3456789"}, format="json")
        assert resp.status_code == 401

    @pytest.mark.django_db
    def test_reports_wrong_key(self, client):
        resp = client.post(
            "/mock-api/reports",
            {"ein": "12-3456789"},
            format="json",
            HTTP_X_API_KEY="wrong"
        )
        assert resp.status_code == 401

    @pytest.mark.django_db
    def test_reports_success(self, client, auth_headers):
        resp = client.post(
            "/mock-api/reports",
            {
                "ein": "12-3456789",
                "ssn": "123-45-6789",
                "wages": "75000",
                "federal_tax_withheld": "12500",
            },
            format="json",
            **auth_headers,
        )
        assert resp.status_code == 201
        assert "report_id" in resp.json()

    @pytest.mark.django_db
    def test_reports_missing_fields(self, client, auth_headers):
        resp = client.post("/mock-api/reports", {"ein": "12-3456789"}, format="json", **auth_headers)
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_files_success(self, client, auth_headers, sample_w2_pdf_content):
        # create report first
        report_resp = client.post(
            "/mock-api/reports",
            {"ein": "12-3456789", "ssn": "123-45-6789", "wages": "75000", "federal_tax_withheld": "12500"},
            format="json",
            **auth_headers,
        )
        report_id = report_resp.json()["report_id"]

        # upload file
        f = io.BytesIO(sample_w2_pdf_content)
        f.name = "w2.pdf"
        resp = client.post(
            "/mock-api/files",
            {"report_id": report_id, "file": f},
            format="multipart",
            **auth_headers,
        )
        assert resp.status_code == 201
        assert "file_id" in resp.json()

    @pytest.mark.django_db
    def test_files_missing_report_id(self, client, auth_headers, sample_w2_pdf_content):
        f = io.BytesIO(sample_w2_pdf_content)
        f.name = "w2.pdf"
        resp = client.post("/mock-api/files", {"file": f}, format="multipart", **auth_headers)
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_files_missing_file(self, client, auth_headers):
        resp = client.post("/mock-api/files", {"report_id": "xxx"}, format="multipart", **auth_headers)
        assert resp.status_code == 400
