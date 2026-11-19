"""Admin registration for subscription plans and tenant subscriptions."""

from django.contrib import admin

from .models import Subscription, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "plan_name",
        "slug",
        "price",
        "discount_price",
        "duration_in_months",
        "max_students",
        "is_popular",
        "is_active",
    )
    list_filter = ("is_active", "is_popular")
    search_fields = ("plan_name", "slug", "description")
    prepopulated_fields = {"slug": ("plan_name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("institute", "plan", "status", "requested_at", "expires_at")
    list_filter = ("status", "plan")
    search_fields = ("institute__institute_name", "institute__institute_id")
    readonly_fields = ("requested_at",)
