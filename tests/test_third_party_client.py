"""Tests for third-party API client"""
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from api.services.third_party_client import ThirdPartyAPIClient, process_w2_with_api
from api.exceptions import (
    ThirdPartyAPIException,
    ThirdPartyAuthenticationException,
    ThirdPartyTimeoutException,
)


class TestThirdPartyAPIClient:

    @pytest.fixture
    def config(self):
        return {
            "base_url": "http://test-api.example.com",
            "api_key": "test-key",
            "timeout": 5,
            "max_retries": 2,
            "retry_delay": 0.1,
        }

    @pytest.mark.asyncio
    async def test_submit_report_success(self, config):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"report_id": "test-123"}

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_resp

            async with ThirdPartyAPIClient(**config) as client:
                result = await client.submit_report({
                    "ein": "12-3456789",
                    "ssn": "123-45-6789",
                    "wages": "75000",
                    "federal_tax_withheld": "12500",
                })

            assert result == "test-123"

    @pytest.mark.asyncio
    async def test_auth_failure(self, config):
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_resp

            async with ThirdPartyAPIClient(**config) as client:
                with pytest.raises(ThirdPartyAuthenticationException):
                    await client.submit_report({"ein": "12-3456789"})

    @pytest.mark.asyncio
    async def test_upload_file_success(self, config):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"file_id": "file-456"}

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_resp

            async with ThirdPartyAPIClient(**config) as client:
                result = await client.upload_file("report-123", b"PDF", "test.pdf")

            assert result == "file-456"

    @pytest.mark.asyncio
    async def test_timeout_raises(self, config):
        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = httpx.TimeoutException("timeout")

            async with ThirdPartyAPIClient(**config) as client:
                with pytest.raises(ThirdPartyTimeoutException):
                    await client.submit_report({})

    @pytest.mark.asyncio
    async def test_retry_on_500(self, config):
        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_500.text = "Server Error"

        resp_201 = MagicMock()
        resp_201.status_code = 201
        resp_201.json.return_value = {"report_id": "test-123"}

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [resp_500, resp_201]

            async with ThirdPartyAPIClient(**config) as client:
                result = await client.submit_report({})

            assert result == "test-123"
            assert mock_req.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_400(self, config):
        resp_400 = MagicMock()
        resp_400.status_code = 400
        resp_400.text = "Bad Request"
        resp_400.json.return_value = {"error": "Invalid"}

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = resp_400

            async with ThirdPartyAPIClient(**config) as client:
                with pytest.raises(ThirdPartyAPIException):
                    await client.submit_report({})

            assert mock_req.call_count == 1  # no retry


class TestProcessW2WithAPI:

    @pytest.mark.asyncio
    async def test_full_flow(self):
        with patch.object(ThirdPartyAPIClient, "submit_report", new_callable=AsyncMock) as mock_submit, \
             patch.object(ThirdPartyAPIClient, "upload_file", new_callable=AsyncMock) as mock_upload:

            mock_submit.return_value = "report-123"
            mock_upload.return_value = "file-456"

            result = await process_w2_with_api(
                {"ein": "12-3456789"},
                b"PDF content",
                "test.pdf",
            )

            assert result["report_id"] == "report-123"
            assert result["file_id"] == "file-456"
