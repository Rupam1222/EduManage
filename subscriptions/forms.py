"""Forms for choosing a subscription plan."""

from django import forms

from .models import SubscriptionPlan


class PlanSelectionForm(forms.Form):
    """Only currently offered plans can be submitted."""

    plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.none(),
        label="Subscription plan",
        widget=forms.RadioSelect,
        empty_label=None,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = SubscriptionPlan.objects.filter(is_active=True)


class RenewalForm(forms.Form):
    """Choose the plan to renew onto; pricing is always recomputed server-side."""

    plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.none(),
        label="Choose your plan",
        widget=forms.RadioSelect,
        empty_label=None,
    )

    def __init__(self, *args, current_plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        plans = SubscriptionPlan.objects.filter(is_active=True)
        if current_plan is not None:
            # Keep the current plan available even if it has been retired so an
            # existing tenant can always renew the plan they are paying for.
            plans = plans | SubscriptionPlan.objects.filter(pk=current_plan.pk)
        self.fields["plan"].queryset = plans.distinct().order_by("price", "plan_name")
