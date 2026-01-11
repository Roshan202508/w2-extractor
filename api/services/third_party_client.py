"""
Async HTTP client for third-party W-2 reporting API

Handles:
- POST /reports - submit extracted data
- POST /files - upload original PDF
"""
import asyncio
import logging

import httpx
from django.conf import settings

from api.exceptions import (
    ThirdPartyAPIException,
    ThirdPartyAuthenticationException,
    ThirdPartyTimeoutException,
)

logger = logging.getLogger(__name__)


class ThirdPartyAPIClient:
    """
    Async client for the third-party API.
    
    Features:
    - Automatic retry with exponential backoff
    - Auth header management
    - Proper error handling
    
    Usage:
        async with ThirdPartyAPIClient() as client:
            report_id = await client.submit_report(data)
            file_id = await client.upload_file(report_id, content, filename)
    """

    def __init__(self, base_url=None, api_key=None, timeout=None, max_retries=None, retry_delay=None):
        self.base_url = base_url or settings.THIRD_PARTY_API_BASE_URL
        self.api_key = api_key or settings.THIRD_PARTY_API_KEY
        self.timeout = timeout or settings.THIRD_PARTY_API_TIMEOUT
        self.max_retries = max_retries or settings.THIRD_PARTY_API_RETRY_COUNT
        self.retry_delay = retry_delay or settings.THIRD_PARTY_API_RETRY_DELAY
        self._client = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers={"X-API-Key": self.api_key},
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def submit_report(self, w2_data: dict) -> str:
        """Submit W-2 data, returns report_id"""
        logger.info("Submitting report to third-party API")

        resp = await self._request("POST", "/reports", json_data=w2_data)

        report_id = resp.get("report_id")
        if not report_id:
            raise ThirdPartyAPIException("Missing report_id in response", code="invalid_response")

        logger.info(f"Report created: {report_id}")
        return report_id

    async def upload_file(self, report_id: str, file_content: bytes, filename: str = "w2.pdf") -> str:
        """Upload PDF file, returns file_id"""
        logger.info(f"Uploading file for report {report_id}")

        files = {"file": (filename, file_content, "application/pdf")}
        data = {"report_id": report_id}

        resp = await self._request("POST", "/files", files=files, data=data)

        file_id = resp.get("file_id")
        if not file_id:
            raise ThirdPartyAPIException("Missing file_id in response", code="invalid_response")

        logger.info(f"File uploaded: {file_id}")
        return file_id

    async def _request(self, method, endpoint, json_data=None, files=None, data=None):
        """Make request with retry logic"""
        if not self._client:
            raise RuntimeError("Client not initialized - use 'async with'")

        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"Request attempt {attempt + 1}/{self.max_retries + 1}: {method} {endpoint}")

                response = await self._client.request(
                    method=method,
                    url=endpoint,
                    json=json_data,
                    files=files,
                    data=data,
                )

                return self._handle_response(response)

            except httpx.TimeoutException as e:
                last_error = ThirdPartyTimeoutException(
                    f"Timeout after {self.timeout}s: {endpoint}",
                    code="timeout",
                )
                logger.warning(f"Timeout (attempt {attempt + 1}): {e}")

            except httpx.RequestError as e:
                last_error = ThirdPartyAPIException(
                    f"Network error: {e}",
                    code="network_error",
                )
                logger.warning(f"Network error (attempt {attempt + 1}): {e}")

            except ThirdPartyAuthenticationException:
                raise  # don't retry auth failures

            except ThirdPartyAPIException as e:
                # only retry 5xx errors
                resp_code = getattr(e, "response_status_code", None)
                if resp_code and 500 <= resp_code < 600:
                    last_error = e
                    logger.warning(f"Server error (attempt {attempt + 1}): {e.detail}")
                else:
                    raise  # don't retry 4xx

            # exponential backoff
            if attempt < self.max_retries:
                delay = self.retry_delay * (2 ** attempt)
                logger.debug(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)

        # all retries failed
        raise last_error or ThirdPartyAPIException("All retries failed", code="max_retries_exceeded")

    def _handle_response(self, response):
        """Parse response and raise exceptions for errors"""
        code = response.status_code

        if code == 401:
            raise ThirdPartyAuthenticationException("Invalid API key", code="auth_failed")

        if 400 <= code < 500:
            try:
                msg = response.json().get("error", response.text)
            except:
                msg = response.text
            exc = ThirdPartyAPIException(f"Client error ({code}): {msg}", code=f"client_error_{code}")
            exc.response_status_code = code
            raise exc

        if code >= 500:
            exc = ThirdPartyAPIException(f"Server error ({code}): {response.text[:200]}", code=f"server_error_{code}")
            exc.response_status_code = code
            raise exc

        if code in (200, 201):
            try:
                return response.json()
            except Exception as e:
                raise ThirdPartyAPIException(f"Invalid JSON response: {e}", code="invalid_json")

        raise ThirdPartyAPIException(f"Unexpected status: {code}", code=f"unexpected_{code}")


# convenience function
async def process_w2_with_api(w2_data, file_content, filename="w2.pdf"):
    """One-shot function to submit report and upload file"""
    async with ThirdPartyAPIClient() as client:
        report_id = await client.submit_report(w2_data)
        file_id = await client.upload_file(report_id, file_content, filename)
        return {"report_id": report_id, "file_id": file_id}
