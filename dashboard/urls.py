from django.urls import path

from dashboard import views


app_name = "dashboard"

urlpatterns = [
    path("", views.OverviewView.as_view(), name="overview"),
    path("payments/", views.PaymentListView.as_view(), name="payments"),
    path("payments/new/", views.PaymentCreateView.as_view(), name="payment-create"),
    path("payments/<uuid:payment_uuid>/", views.PaymentDetailView.as_view(), name="payment-detail"),
    path(
        "payments/<uuid:payment_uuid>/process/",
        views.PaymentProcessView.as_view(),
        name="payment-process",
    ),
    path("activity/", views.ActivityView.as_view(), name="activity"),
]
