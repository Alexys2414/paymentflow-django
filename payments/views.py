"""Adaptadores HTTP del dominio de pagos."""

from __future__ import annotations

from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.gateways.mock import MockPaymentGateway, MockPaymentOutcome
from payments.models import PaymentRequest
from payments.serializers import (
    PaymentAdminSerializer,
    PaymentCreateSerializer,
    PaymentEventSerializer,
    PaymentProcessSerializer,
    PublicPaymentSerializer,
)
from payments.services.payments import (
    CreatePaymentRequestCommand,
    IdempotencyConflictError,
    InvalidPaymentTransitionError,
    PaymentService,
)


class PaymentListCreateAPIView(generics.ListAPIView):
    serializer_class = PaymentAdminSerializer
    queryset = PaymentRequest.objects.all()

    def post(self, request: Request) -> Response:
        serializer = PaymentCreateSerializer(
            data=request.data,
            context={"idempotency_key": request.headers.get("Idempotency-Key")},
        )
        serializer.is_valid(raise_exception=True)

        try:
            result = PaymentService.create(
                CreatePaymentRequestCommand(
                    amount=serializer.validated_data["amount"],
                    concept=serializer.validated_data["concept"],
                    reference=serializer.validated_data["reference"],
                    expires_at=serializer.validated_data.get("expires_at"),
                    idempotency_key=request.headers["Idempotency-Key"],
                )
            )
        except IdempotencyConflictError:
            return Response(
                {"detail": "La clave de idempotencia ya se usó con datos distintos."},
                status=status.HTTP_409_CONFLICT,
            )

        response_status = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
        return Response(PaymentAdminSerializer(result.payment).data, status=response_status)


class PaymentDetailAPIView(APIView):
    def get(self, request: Request, payment_uuid: UUID) -> Response:
        payment = _get_payment(payment_uuid)
        return Response(PaymentAdminSerializer(payment).data)


class PaymentProcessAPIView(APIView):
    def post(self, request: Request, payment_uuid: UUID) -> Response:
        serializer = PaymentProcessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = _get_payment(payment_uuid)

        try:
            result = PaymentService.process(
                payment.pk,
                MockPaymentGateway(MockPaymentOutcome(serializer.validated_data["outcome"])),
            )
        except InvalidPaymentTransitionError:
            return Response(
                {"detail": "El pago no se puede procesar en su estado actual."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serialized_payment = PaymentAdminSerializer(result.payment).data
        if not result.gateway_available:
            return Response(
                {
                    "detail": "La pasarela simulada no está disponible; el pago sigue pendiente.",
                    "payment": serialized_payment,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(serialized_payment)


class PaymentEventListAPIView(APIView):
    def get(self, request: Request, payment_uuid: UUID) -> Response:
        payment = _get_payment(payment_uuid)
        events = payment.events.all()
        return Response(PaymentEventSerializer(events, many=True).data)


class PublicPaymentDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, token: str) -> Response:
        payment = get_object_or_404(PaymentRequest, public_token=token)
        return Response(PublicPaymentSerializer(payment).data)


def _get_payment(payment_uuid: UUID) -> PaymentRequest:
    return get_object_or_404(PaymentRequest, uuid=payment_uuid)
