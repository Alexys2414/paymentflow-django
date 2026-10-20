"""Vistas HTML del dashboard. La lógica de dominio sigue en PaymentService."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from dashboard.forms import PaymentRequestForm
from payments.gateways.mock import MockPaymentGateway, MockPaymentOutcome
from payments.models import PaymentEvent, PaymentRequest, PaymentStatus
from payments.services.payments import (
    CreatePaymentRequestCommand,
    IdempotencyConflictError,
    InvalidPaymentTransitionError,
    PaymentService,
)


STATUS_LABELS = {
    PaymentStatus.PAID: "Completed",
    PaymentStatus.PENDING: "Pending",
    PaymentStatus.FAILED: "Failed",
    PaymentStatus.EXPIRED: "Expired",
}

STATUS_EXPLANATIONS = {
    "payment_request.created": "La solicitud se creó y quedó lista para procesarse.",
    "payment_request.status_changed": "El resultado de la pasarela actualizó el estado.",
    "payment_request.expired": "La solicitud superó su fecha de expiración antes de procesarse.",
    "payment.gateway_communication_failed": "La pasarela no respondió; el pago sigue pendiente.",
}


class DashboardAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = "/api-auth/login/"

    def test_func(self) -> bool:
        return self.request.user.is_staff

    def handle_no_permission(self) -> HttpResponse:
        if self.request.user.is_authenticated:
            return HttpResponseForbidden("Staff access is required.")
        return super().handle_no_permission()


class DashboardContextMixin(DashboardAccessMixin):
    active_nav = ""
    page_title = ""

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "active_nav": self.active_nav,
                "page_title": self.page_title,
                "status_labels": STATUS_LABELS,
            }
        )
        return context


class OverviewView(DashboardContextMixin, TemplateView):
    template_name = "dashboard/overview.html"
    active_nav = "overview"
    page_title = "Overview"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        aggregate = PaymentRequest.objects.aggregate(
            total_processed=Sum("amount", filter=Q(status=PaymentStatus.PAID)),
            approved_count=Count("id", filter=Q(status=PaymentStatus.PAID)),
            pending_count=Count("id", filter=Q(status=PaymentStatus.PENDING)),
            failed_count=Count("id", filter=Q(status=PaymentStatus.FAILED)),
        )
        distribution = {
            item["status"]: item["count"]
            for item in PaymentRequest.objects.values("status").annotate(count=Count("id"))
        }
        total_count = sum(distribution.values())
        context.update(
            {
                "total_processed": aggregate["total_processed"] or Decimal("0.00"),
                "approved_count": aggregate["approved_count"] or 0,
                "pending_count": aggregate["pending_count"] or 0,
                "failed_count": aggregate["failed_count"] or 0,
                "recent_payments": PaymentRequest.objects.all()[:6],
                "distribution": [
                    {
                        "status": status,
                        "label": STATUS_LABELS[status],
                        "count": distribution.get(status, 0),
                        "percentage": round(distribution.get(status, 0) / total_count * 100)
                        if total_count
                        else 0,
                    }
                    for status in PaymentStatus.values
                ],
                "total_count": total_count,
            }
        )
        return context


class PaymentListView(DashboardContextMixin, TemplateView):
    template_name = "dashboard/payments.html"
    active_nav = "payments"
    page_title = "Payments"
    page_size = 12
    ordering_fields = {
        "newest": "-created_at",
        "oldest": "created_at",
        "amount_desc": "-amount",
        "amount_asc": "amount",
    }

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()
        selected_status = self.request.GET.get("status", "")
        sort = self.request.GET.get("sort", "newest")
        payments = PaymentRequest.objects.all()

        if query:
            payments = payments.filter(
                Q(reference__icontains=query)
                | Q(concept__icontains=query)
                | Q(uuid__icontains=query)
            )
        if selected_status in PaymentStatus.values:
            payments = payments.filter(status=selected_status)

        payments = payments.order_by(self.ordering_fields.get(sort, "-created_at"))
        paginator = Paginator(payments, self.page_size)
        page = paginator.get_page(self.request.GET.get("page"))
        counts = {
            item["status"]: item["count"]
            for item in PaymentRequest.objects.values("status").annotate(count=Count("id"))
        }
        context.update(
            {
                "payments": page,
                "query": query,
                "selected_status": selected_status,
                "sort": sort,
                "status_counts": counts,
                "statuses": PaymentStatus,
            }
        )
        return context


class PaymentDetailView(DashboardContextMixin, TemplateView):
    template_name = "dashboard/payment_detail.html"
    active_nav = "payments"
    page_title = "Payment detail"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        payment = get_object_or_404(PaymentRequest, uuid=self.kwargs["payment_uuid"])
        events = payment.events.all()
        context.update(
            {
                "payment": payment,
                "events": events,
                "event_explanations": STATUS_EXPLANATIONS,
                "can_process": payment.status == PaymentStatus.PENDING
                and (payment.expires_at is None or payment.expires_at > timezone.now()),
            }
        )
        return context


class ActivityView(DashboardContextMixin, TemplateView):
    template_name = "dashboard/activity.html"
    active_nav = "activity"
    page_title = "Activity"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["events"] = PaymentEvent.objects.select_related("payment_request").all()[:50]
        return context


class PaymentCreateView(DashboardAccessMixin, View):
    template_name = "dashboard/payment_create.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return self._render(request, PaymentRequestForm(initial=self._initial_data()))

    def post(self, request: HttpRequest) -> HttpResponse:
        form = PaymentRequestForm(request.POST)
        if not form.is_valid():
            return self._render(request, form)

        try:
            result = PaymentService.create(
                CreatePaymentRequestCommand(
                    amount=form.cleaned_data["amount"],
                    concept=form.cleaned_data["concept"],
                    reference=form.cleaned_data["reference"],
                    idempotency_key=form.cleaned_data["idempotency_key"],
                )
            )
        except IdempotencyConflictError:
            form.add_error(None, "La solicitud ya existe con datos diferentes. Genera una nueva.")
            return self._render(request, form)

        if result.created:
            messages.success(request, "Payment request created successfully.")
        else:
            messages.info(request, "Existing payment request recovered safely.")
        return redirect("dashboard:payment-detail", payment_uuid=result.payment.uuid)

    def _initial_data(self) -> dict[str, str]:
        return {"idempotency_key": f"dashboard-{uuid.uuid4()}"}

    def _render(self, request: HttpRequest, form: PaymentRequestForm) -> HttpResponse:
        from django.shortcuts import render

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "active_nav": "payments",
                "page_title": "Create payment",
                "status_labels": STATUS_LABELS,
            },
        )


class PaymentProcessView(DashboardAccessMixin, View):
    def post(self, request: HttpRequest, payment_uuid: uuid.UUID) -> HttpResponse:
        payment = get_object_or_404(PaymentRequest, uuid=payment_uuid)
        outcome = request.POST.get("outcome")
        try:
            mock_outcome = MockPaymentOutcome(outcome)
            result = PaymentService.process(payment.pk, MockPaymentGateway(mock_outcome))
        except ValueError:
            messages.error(request, "Unsupported development simulation.")
        except InvalidPaymentTransitionError:
            messages.warning(request, "This payment can no longer be processed.")
        else:
            if result.gateway_available:
                messages.success(request, "Development simulation completed.")
            else:
                messages.warning(request, "Gateway unavailable. The payment remains pending.")
        return redirect("dashboard:payment-detail", payment_uuid=payment.uuid)
