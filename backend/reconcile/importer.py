import csv
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.db import transaction

from .models import Location, SystemARecord, SystemBRecord
from .normalization import normalize_record_ref

logger = logging.getLogger(__name__)


class ImportDataError(ValueError):
    pass


def parse_decimal(value, file_name=None, row_number=None, field_name=None):
    if value is None or not str(value).strip():
        return None
    normalized = str(value).strip().replace(",", "")
    try:
        amount = Decimal(normalized)
        if not amount.is_finite():
            raise InvalidOperation
        return amount
    except InvalidOperation:
        logger.warning(
            "%s row %s has invalid %s value %r; storing NULL and preserving raw data",
            file_name or "CSV",
            row_number or "?",
            field_name or "decimal",
            value,
        )
        return None


def _parse_date(value, file_name, row_number):
    if not value or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        logger.warning(
            "%s row %s has invalid date %r; storing NULL and preserving raw data",
            file_name,
            row_number,
            value,
        )
        return None


def _read_csv(path, required_headers):
    if not path.is_file():
        raise ImportDataError(f"Missing CSV file: {path}")
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ImportDataError(f"{path.name} has no header row")
        missing = set(required_headers) - set(reader.fieldnames)
        if missing:
            raise ImportDataError(
                f"{path.name} is missing required headers: {', '.join(sorted(missing))}"
            )
        return list(reader)


def import_data(data_dir=None):
    directory = Path(data_dir) if data_dir else Path(settings.BASE_DIR) / "data"
    locations = _read_csv(directory / "locations.csv", ("location_id", "org_id"))
    system_a = _read_csv(
        directory / "system_a.csv",
        ("record_id", "location_id", "event_date", "base_value", "adjustment",
         "total_value", "state", "actor_id"),
    )
    system_b = _read_csv(
        directory / "system_b.csv",
        ("entry_id", "record_ref", "location_id", "recorded_on", "value"),
    )

    saved_a = 0
    saved_b = 0
    with transaction.atomic():
        for row in locations:
            location_id = row["location_id"].strip()
            Location.objects.update_or_create(
                location_id=location_id,
                defaults={
                    "org_id": row["org_id"].strip(),
                    "location_name": (row.get("location_name") or "").strip(),
                },
            )
        known_location_ids = set(
            Location.objects.values_list("location_id", flat=True)
        )

        for row_number, row in enumerate(system_a, start=2):
            record_id = row["record_id"].strip()
            location_id = row["location_id"].strip()
            if location_id not in known_location_ids:
                logger.warning(
                    "system_a.csv row %s has unknown location %r; saving record "
                    "without a location relation and preserving raw data",
                    row_number,
                    location_id,
                )
            SystemARecord.objects.update_or_create(
                record_id=record_id,
                defaults={
                    "location_id": location_id if location_id in known_location_ids else None,
                    "event_date": _parse_date(row["event_date"], "system_a.csv", row_number),
                    "category_code": (row.get("category_code") or "").strip(),
                    "base_value": parse_decimal(
                        row.get("base_value"), "system_a.csv", row_number, "base_value"
                    ),
                    "adjustment": parse_decimal(
                        row.get("adjustment"), "system_a.csv", row_number, "adjustment"
                    ),
                    "total_value": parse_decimal(
                        row.get("total_value"), "system_a.csv", row_number, "total_value"
                    ),
                    "state": (row.get("state") or "").strip(),
                    "actor_id": (row.get("actor_id") or "").strip() or None,
                    "raw_data": row,
                },
            )
            saved_a += 1

        for row_number, row in enumerate(system_b, start=2):
            SystemBRecord.objects.update_or_create(
                entry_id=row["entry_id"].strip(),
                defaults={
                    "record_ref": row.get("record_ref") or "",
                    "normalized_ref": normalize_record_ref(row.get("record_ref")),
                    "location_id": row["location_id"].strip(),
                    "recorded_on": _parse_date(
                        row["recorded_on"], "system_b.csv", row_number
                    ),
                    "value": parse_decimal(
                        row.get("value"), "system_b.csv", row_number, "value"
                    ),
                    "raw_data": row,
                },
            )
            saved_b += 1

    return {
        "locations": len(locations),
        "system_a": len(system_a),
        "system_b": len(system_b),
        "system_a_saved": saved_a,
        "system_b_saved": saved_b,
        "blank_actor_ids": sum(not (row.get("actor_id") or "").strip() for row in system_a),
        "blank_values": sum(not (row.get("value") or "").strip() for row in system_b),
        "normalized_refs": sum(
            bool(normalize_record_ref(row.get("record_ref")))
            and normalize_record_ref(row.get("record_ref"))
            != (row.get("record_ref") or "").strip().upper()
            for row in system_b
        ),
    }
