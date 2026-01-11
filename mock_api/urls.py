from django.urls import path
from .views import MockReportView, MockFileUploadView

app_name = "mock_api"

urlpatterns = [
    path("reports", MockReportView.as_view(), name="reports"),
    path("files", MockFileUploadView.as_view(), name="files"),
]
