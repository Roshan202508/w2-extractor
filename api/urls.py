from django.urls import path
from .views import HealthCheckView, W2ProcessView

app_name = "api"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("w2/process/", W2ProcessView.as_view(), name="w2-process"),
]
