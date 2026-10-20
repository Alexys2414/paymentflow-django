from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthenticationRedirectTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="staff-user",
            password="test-password",
            is_staff=True,
        )

    def test_drf_login_redirects_to_payment_list(self) -> None:
        response = self.client.post(
            reverse("rest_framework:login"),
            {"username": "staff-user", "password": "test-password"},
        )

        self.assertRedirects(response, "/api/payments/", fetch_redirect_response=False)

    def test_admin_login_keeps_admin_destination(self) -> None:
        response = self.client.post(
            reverse("admin:login"),
            {
                "username": "staff-user",
                "password": "test-password",
                "next": "/admin/",
            },
        )

        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)
