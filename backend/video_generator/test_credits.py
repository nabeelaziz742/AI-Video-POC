from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from .credits import FREE_MONTHLY_CREDITS, generation_cost, get_or_create_credit_account, reserve_generation
from .models import CreditTransaction, VideoProject


class CreditServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="credit-user", password="pass12345")
        self.project = VideoProject.objects.create(user=self.user, title="Credit test", prompt="A test", duration=10)

    def test_new_user_gets_free_allowance_once(self):
        account = get_or_create_credit_account(self.user)
        self.assertEqual(account.balance, FREE_MONTHLY_CREDITS)
        self.assertEqual(CreditTransaction.objects.filter(account=account, kind=CreditTransaction.Kind.GRANT).count(), 1)
        same = get_or_create_credit_account(self.user)
        self.assertEqual(same.balance, FREE_MONTHLY_CREDITS)
        self.assertEqual(CreditTransaction.objects.filter(account=account, kind=CreditTransaction.Kind.GRANT).count(), 1)

    def test_reservation_is_atomic_and_idempotent(self):
        self.assertEqual(generation_cost(10), 10)
        self.assertEqual(reserve_generation(self.user, self.project, idempotency_key="credit-test-1"), 10)
        self.assertEqual(reserve_generation(self.user, self.project, idempotency_key="credit-test-1"), 10)
        account = get_or_create_credit_account(self.user)
        self.assertEqual(account.balance, FREE_MONTHLY_CREDITS - 10)
        self.assertEqual(CreditTransaction.objects.filter(kind=CreditTransaction.Kind.RESERVE).count(), 1)

    def test_insufficient_balance_rejected(self):
        account = get_or_create_credit_account(self.user)
        account.balance = 0
        account.save(update_fields=["balance"])
        with self.assertRaises(ValidationError):
            reserve_generation(self.user, self.project, idempotency_key="credit-test-low")
