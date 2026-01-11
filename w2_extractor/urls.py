"""
URL configuration for w2_extractor project.
"""

from django.urls import include, path

urlpatterns = [
    # Main API endpoints
    path("api/", include("api.urls")),
    # Mock third-party API (for testing/development)
    path("mock-api/", include("mock_api.urls")),
]

