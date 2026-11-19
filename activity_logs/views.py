"""Institute-scoped activity log workspace (Super Admin uses its console)."""

from django.db.models import Q
from django.shortcuts import render

from accounts.decorators import institute_admin_required

from .models import ActivityLog


@institute_admin_required
def institute_activity_logs(request):
    """Show only the signed-in admin's institute activity."""
    rows = (
        ActivityLog.objects.filter(institute=request.user.institute)
        .select_related("user", "institute")
    )
    query = request.GET.get("q", "").strip()
    action = request.GET.get("action", "").strip()

    if query:
        rows = rows.filter(
            Q(action__icontains=query)
            | Q(description__icontains=query)
            | Q(user__email__icontains=query)
            | Q(ip_address__icontains=query)
        )
    if action:
        rows = rows.filter(action=action)

    action_choices = (
        ActivityLog.objects.filter(institute=request.user.institute)
        .order_by("action")
        .values_list("action", flat=True)
        .distinct()
    )

    return render(
        request,
        "activity_logs/institute_list.html",
        {
            "logs": rows[:200],
            "query": query,
            "action": action,
            "action_choices": action_choices,
        },
    )
