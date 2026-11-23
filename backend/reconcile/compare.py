from collections import defaultdict
from decimal import Decimal

from .normalization import normalize_record_ref


def _decimal(value):
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _as_text(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _value(value):
    return str(value) if value is not None else None


def _difference(a_value, b_value):
    if a_value is None or b_value is None:
        return None
    return str(b_value - a_value)


def _entry_ref(entry):
    return entry.get("normalized_ref") or normalize_record_ref(entry.get("record_ref"))


def _entry_details(entries):
    details = []
    for entry in entries:
        raw_data = entry.get("raw_data") or {}
        details.append(
            {
                "entry_id": entry["entry_id"],
                "record_ref": entry.get("record_ref", ""),
                "normalized_ref": _entry_ref(entry),
                "location_id": entry["location_id"],
                "recorded_on": _as_text(entry.get("recorded_on")),
                "value": _value(_decimal(entry.get("value"))),
                "label": raw_data.get("label", entry.get("label", "")),
            }
        )
    return details


def _item(
    *,
    record_id,
    location_id,
    location_names,
    org_id,
    reason,
    a_value=None,
    b_value=None,
    details=None,
):
    a_text = _value(a_value)
    b_text = _value(b_value)
    return {
        "record_id": record_id,
        "location_id": location_id,
        "location_name": location_names.get(location_id, ""),
        "location": location_id,
        "org_id": org_id,
        "reason": reason,
        "system_a_value": a_text,
        "system_b_value": b_text,
        "a_value": a_text,
        "b_value": b_text,
        "difference": _difference(a_value, b_value),
        "details": details or {},
    }


def compare_records(a_rows, b_rows, location_orgs, location_names, org_id):
    """Compare tenant-scoped plain records; this function performs no database access."""
    tenant_location_ids = {
        location_id
        for location_id, location_org in location_orgs.items()
        if location_org == org_id
    }
    a_records = [
        row for row in a_rows if row.get("location_id") in tenant_location_ids
    ]
    b_entries = [
        row for row in b_rows if row.get("location_id") in tenant_location_ids
    ]

    a_by_ref = {
        normalize_record_ref(record.get("record_id")): record
        for record in a_records
    }
    b_by_ref = defaultdict(list)
    for entry in b_entries:
        b_by_ref[_entry_ref(entry)].append(entry)

    disagreements = []
    for record in a_records:
        record_id = record["record_id"]
        location_id = record["location_id"]
        a_value = _decimal(record.get("total_value"))
        candidates = [
            entry
            for entry in b_by_ref.get(normalize_record_ref(record_id), [])
            if entry.get("location_id") == location_id
        ]

        if not candidates:
            disagreements.append(
                _item(
                    record_id=record_id,
                    location_id=location_id,
                    location_names=location_names,
                    org_id=org_id,
                    reason="MISSING_IN_B",
                    a_value=a_value,
                    details={
                        "message": "No System B entry matches this record and location."
                    },
                )
            )
            continue

        if any(entry.get("value") is None for entry in candidates):
            disagreements.append(
                _item(
                    record_id=record_id,
                    location_id=location_id,
                    location_names=location_names,
                    org_id=org_id,
                    reason="MISSING_VALUE_IN_B",
                    a_value=a_value,
                    details={"entries": _entry_details(candidates)},
                )
            )
            continue

        values = [_decimal(entry.get("value")) for entry in candidates]
        aggregate = sum(values, Decimal("0"))
        if len(candidates) > 1:
            if a_value is not None and aggregate == a_value:
                continue
            disagreements.append(
                _item(
                    record_id=record_id,
                    location_id=location_id,
                    location_names=location_names,
                    org_id=org_id,
                    reason="DUPLICATE_IN_B",
                    a_value=a_value,
                    b_value=aggregate,
                    details={
                        "entries": _entry_details(candidates),
                        "aggregate_value": _value(aggregate),
                        "aggregate_matches_system_a": aggregate == a_value,
                        "message": "Multiple System B entries do not sum to System A's total.",
                    },
                )
            )
            continue

        b_value = values[0]
        if a_value != b_value:
            disagreements.append(
                _item(
                    record_id=record_id,
                    location_id=location_id,
                    location_names=location_names,
                    org_id=org_id,
                    reason="VALUE_MISMATCH",
                    a_value=a_value,
                    b_value=b_value,
                    details={"entries": _entry_details(candidates)},
                )
            )

    for entry in b_entries:
        record = a_by_ref.get(_entry_ref(entry))
        if record is not None and record.get("location_id") == entry.get("location_id"):
            continue
        location_id = entry["location_id"]
        disagreements.append(
            _item(
                record_id=_entry_ref(entry),
                location_id=location_id,
                location_names=location_names,
                org_id=org_id,
                reason="ORPHAN_IN_B",
                b_value=_decimal(entry.get("value")),
                details={
                    "entries": _entry_details([entry]),
                    "message": "System B entry has no System A record at this tenant and location.",
                },
            )
        )

    return disagreements


def value_sort_key(item):
    value = item["system_b_value"]
    if value is None:
        value = item["system_a_value"]
    return Decimal(value) if value is not None else None
