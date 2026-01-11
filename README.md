# W-2 Extractor Service

An asynchronous Django REST API that processes W-2 PDF forms, extracts tax data, and reports it to a third-party service.

## Overview

This service accepts W-2 PDF uploads, extracts key tax information (EIN, SSN, wages, federal tax withheld), and submits the data to an external reporting API. It's designed to be stateless, resilient, and production-ready.

### Key Features

- **PDF Processing** - Extracts text from W-2 PDFs using PyMuPDF
- **Data Extraction** - Uses regex patterns and label-based search to find tax fields
- **Async HTTP Client** - Non-blocking external API calls with retry logic
- **Error Handling** - Consistent error responses with proper HTTP status codes
- **Mock API** - Built-in mock for development and testing

### How It Works

```
┌──────────┐     ┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Client  │────▶│  W-2 Extractor  │────▶│  Extract Data    │────▶│  Third-Party    │
│          │     │  POST /api/w2/  │     │  from PDF        │     │  API            │
│          │◀────│  process/       │◀────│                  │◀────│  /reports       │
│          │     │                 │     │                  │     │  /files         │
└──────────┘     └─────────────────┘     └──────────────────┘     └─────────────────┘
```

---

## Project Structure

```
w2-extractor/
├── w2_extractor/        # Django project configuration
├── api/                 # Main API (endpoints, services, validation)
│   └── services/        # Business logic (PDF extraction, HTTP client)
├── mock_api/            # Mock third-party API for development
├── tests/               # Test suite
├── pyproject.toml       # Dependencies (Poetry)
├── Dockerfile           # Container build
└── docker-compose.yml   # Local development
```



---

## Getting Started

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation) (recommended) or pip

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd w2-extractor

# Install dependencies with Poetry
poetry install

# Activate virtual environment
poetry shell

# Run the development server
uvicorn w2_extractor.asgi:application --reload --port 8000
```

The API will be available at `http://localhost:8000`

### Alternative: Docker

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or run in background
docker-compose up -d
```

---

## Development Guide

### Running Tests

```bash
# Run all tests
poetry run pytest -v

# Run with coverage
poetry run pytest --cov=api --cov-report=html

# Run specific test file
poetry run pytest tests/test_pdf_extractor.py -v
```

### Code Quality

```bash
# Format code
poetry run black .
poetry run isort .

# Lint
poetry run flake8
```

### Project Workflow

1. **Make changes** to the code
2. **Run tests** to ensure nothing is broken
3. **Format code** with black/isort before committing

### Key Files for New Contributors

| Want to... | Look at |
|------------|---------|
| Understand the API endpoint | `api/views.py` |
| Modify PDF extraction logic | `api/services/pdf_extractor.py` |
| Change third-party API behavior | `api/services/third_party_client.py` |
| Add validation rules | `api/serializers.py` |
| Add new error types | `api/exceptions.py` |
| Modify mock API | `mock_api/views.py` |
| Add test fixtures | `conftest.py` |

---

## API Reference

### Health Check

```bash
curl http://localhost:8000/api/health/
```

```json
{
  "status": "healthy",
  "service": "w2-extractor",
  "version": "1.0.0"
}
```

### Process W-2

```bash
curl -X POST http://localhost:8000/api/w2/process/ \
  -F "file=@path/to/w2.pdf"
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "W-2 processed successfully",
  "data": {
    "report_id": "550e8400-e29b-41d4-a716-446655440000",
    "file_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
  },
  "extracted_data": {
    "ein": "12-3456789",
    "ssn": "123-45-6789",
    "wages": "75000.00",
    "federal_tax_withheld": "12500.00"
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": {
    "code": "invalid_file",
    "message": "Only PDF files are accepted."
  }
}
```

---

## Mock API

For development, a mock third-party API is included at `/mock-api/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mock-api/reports` | POST | Submit W-2 data, returns `report_id` |
| `/mock-api/files` | POST | Upload PDF file, returns `file_id` |

**Authentication:** All requests require header `X-API-Key: FinPro-Secret-Key`

---

## Configuration

Environment variables (can be set in `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `True` | Enable debug mode |
| `DJANGO_SECRET_KEY` | dev key | Django secret key |
| `THIRD_PARTY_API_BASE_URL` | `http://localhost:8000/mock-api` | External API URL |
| `THIRD_PARTY_API_KEY` | `FinPro-Secret-Key` | API key for external service |
| `THIRD_PARTY_API_TIMEOUT` | `30` | Request timeout in seconds |
| `THIRD_PARTY_API_RETRY_COUNT` | `3` | Max retry attempts |

---

## Documentation

- **[DESIGN.md](DESIGN.md)** - Architecture decisions, assumptions, and trade-offs
- **[DOCUMENTATION.md](DOCUMENTATION.md)** - Detailed explanation of each file and component

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | Django 4.2 + Django REST Framework |
| PDF Parsing | PyMuPDF (fitz) |
| HTTP Client | httpx (async) |
| Server | uvicorn (ASGI) |
| Package Manager | Poetry |
| Testing | pytest + pytest-asyncio |
