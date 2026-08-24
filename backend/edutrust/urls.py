from django.urls import path, include
from edutrust_api import views

urlpatterns = [
    path("health", views.health),
    path("ready", views.ready),
    path("api/v1/", include("edutrust_api.urls")),
]
