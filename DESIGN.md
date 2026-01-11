# Design Notes

## Architecture

```
Client -> API View -> PDF Extractor -> Third-Party Client (async) -> External API
```

The API view handles HTTP, the extractor pulls data from PDFs, and the async client talks to the external service.

## Key decisions

### Async implementation

The requirement specifies "the API must be asynchronous". The implementation uses:

1. **Async HTTP client** (`httpx.AsyncClient`) - Non-blocking I/O for third-party API calls
2. **`async_to_sync` wrapper** - Bridges DRF's sync views with async processing
3. **ASGI server** (uvicorn) - Enables async Django

**Why not pure async views?**

DRF's `APIView.dispatch()` is synchronous. Using `async def post()` directly returns a coroutine, not a Response. Until DRF adds proper async support, we use `async_to_sync` to run async code from sync views.

The actual I/O operations (third-party API calls) are still async - they don't block the event loop.

### PDF extraction

Using PyMuPDF (`fitz`) for text extraction - fast and reliable.

W-2 forms are standardized but vary in generation. Multi-strategy approach:

1. Look for labels ("Employer identification number", etc) and find values nearby
2. Fall back to regex patterns for EIN/SSN formats
3. Apply validation rules (EINs don't start with 9, SSN area rules)

### Retry logic

Third-party client retries on:
- Network errors
- Timeouts  
- 5xx server errors

Does NOT retry on:
- 4xx client errors (our fault)
- 401 auth errors

Uses exponential backoff: 1s, 2s, 4s, etc.

### Error handling

All errors return consistent format:
```json
{
  "success": false,
  "error": {
    "code": "error_code",
    "message": "description"
  }
}
```

Custom DRF exception handler ensures this across all error types.

## Assumptions

1. **Text-based PDFs only** - No OCR. Scanned PDFs fail with clear error.

2. **Single file per request** - Batch processing would be separate endpoint.

3. **Stateless service** - We don't store data. Goes straight to third-party API.

4. **No auth on our API** - Could be added if needed.

5. **10MB file limit** - W-2s are usually small.

6. **Sequential API calls** - /reports must succeed before /files.

7. **Third-party API idempotency** - Assumed NOT idempotent.

## Third-party API spec (mocked)

- `POST /reports` - JSON body with W-2 data, returns `{report_id}`
- `POST /files` - multipart with report_id and file, returns `{file_id}`
- Auth via `X-API-Key: FinPro-Secret-Key` header

## Running

```bash
# Development
poetry run uvicorn w2_extractor.asgi:application --reload

# Production  
poetry run uvicorn w2_extractor.asgi:application --host 0.0.0.0 --port 8000

# Docker
docker-compose up
```

## Testing

```bash
poetry run pytest -v
```
