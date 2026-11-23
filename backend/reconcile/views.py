from rest_framework.decorators import api_view
from rest_framework.response import Response

from .compare import compare_records, value_sort_key
from .models import Location, SystemARecord, SystemBRecord


@api_view(["GET"])
def orgs(request):
    available = list(
        Location.objects.order_by("org_id")
        .values_list("org_id", flat=True)
        .distinct()
    )
    return Response(available)


@api_view(["GET"])
def disagreements(request):
    org_id = request.query_params.get("org")
    if not org_id:
        return Response({"detail": "The org query parameter is required."}, status=400)

    available_orgs = set(Location.objects.values_list("org_id", flat=True).distinct())
    if org_id not in available_orgs:
        return Response({"detail": f"Unknown org: {org_id}."}, status=400)

    reason = request.query_params.get("reason")
    sort_order = request.query_params.get("sort", "asc")
    sort_descending = sort_order in {"desc", "-value"}
    if sort_order not in {"asc", "desc", "value", "-value"}:
        return Response(
            {"detail": "sort must be 'asc', 'desc', 'value', or '-value'."},
            status=400,
        )

    location_rows = list(
        Location.objects.filter(org_id=org_id).values(
            "location_id", "org_id", "location_name"
        )
    )
    location_orgs = {row["location_id"]: row["org_id"] for row in location_rows}
    location_names = {
        row["location_id"]: row["location_name"] for row in location_rows
    }
    location_ids = list(location_orgs)
    a_rows = list(
        SystemARecord.objects.filter(location__org_id=org_id).values(
            "record_id",
            "location_id",
            "event_date",
            "base_value",
            "adjustment",
            "total_value",
            "state",
            "actor_id",
            "category_code",
        )
    )
    b_rows = list(
        SystemBRecord.objects.filter(location_id__in=location_ids).values(
            "entry_id",
            "record_ref",
            "normalized_ref",
            "location_id",
            "recorded_on",
            "value",
            "raw_data",
        )
    )
    items = compare_records(a_rows, b_rows, location_orgs, location_names, org_id)
    if reason:
        items = [item for item in items if item["reason"] == reason]

    valued_items = [item for item in items if value_sort_key(item) is not None]
    missing_value_items = [item for item in items if value_sort_key(item) is None]
    valued_items.sort(key=value_sort_key, reverse=sort_descending)
    return Response(valued_items + missing_value_items)
