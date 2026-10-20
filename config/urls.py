"""Rutas HTTP del proyecto."""

from django.contrib import admin
from django.urls import include, path

from payments import views


urlpatterns = [
    path("dashboard/", include("dashboard.urls")),
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("api/payments/", views.PaymentListCreateAPIView.as_view(), name="payment-list"),
    path(
        "api/payments/<uuid:payment_uuid>/",
        views.PaymentDetailAPIView.as_view(),
        name="payment-detail",
    ),
    path(
        "api/payments/<uuid:payment_uuid>/process/",
        views.PaymentProcessAPIView.as_view(),
        name="payment-process",
    ),
    path(
        "api/payments/<uuid:payment_uuid>/events/",
        views.PaymentEventListAPIView.as_view(),
        name="payment-events",
    ),
    path("pay/<str:token>/", views.PublicPaymentDetailAPIView.as_view(), name="public-payment"),
]
