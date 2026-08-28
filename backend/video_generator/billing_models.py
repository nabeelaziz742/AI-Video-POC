from django.conf import settings
from django.db import models


class Subscription(models.Model):
    class Plan(models.TextChoices):
        FREE = "free", "Free"
        CREATOR = "creator", "Creator"
        PRO = "pro", "Pro"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRIALING = "trialing", "Trialing"
        PAST_DUE = "past_due", "Past due"
        CANCELLED = "cancelled", "Cancelled"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="subscription", on_delete=models.CASCADE)
    plan_code = models.CharField(max_length=30, choices=Plan.choices, default=Plan.FREE)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ACTIVE)
    provider = models.CharField(max_length=30, default="manual")
    provider_customer_id = models.CharField(max_length=120, blank=True)
    provider_subscription_id = models.CharField(max_length=120, blank=True)
    current_period_start = models.DateTimeField(blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.plan_code}"
