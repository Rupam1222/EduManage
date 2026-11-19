"""Server-enforced tenant APIs.

These views intentionally avoid trusting query parameters such as
``?institute_id=``. The tenant is always derived from the authenticated user.
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .tenant import (
    institute_for_request,
    resolve_tenant_model,
    scoped_queryset,
    search_tenant_data,
)


@login_required
def search_api(request):
    """JSON tenant search across every registered tenant model."""
    institute = institute_for_request(request)
    results = search_tenant_data(request.GET.get("q", ""), institute)
    return JsonResponse({"results": results, "count": len(results)})


@login_required
def records_api(request, app_label, model_name):
    """JSON list of one tenant model, always scoped to the request's tenant."""
    model = resolve_tenant_model(app_label, model_name)
    queryset = scoped_queryset(model, request)
    records = [
        {
            "pk": item.pk,
            "label": str(item),
            "institute_id": item.institute_id,
        }
        for item in queryset[:100]
    ]
    return JsonResponse(
        {
            "model": model._meta.model_name,
            "institute_id": (
                None if institute_for_request(request) is None else request.user.institute_id
            ),
            "count": len(records),
            "results": records,
        }
    )
