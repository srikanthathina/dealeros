import csv
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from reconcile.compare import compare_records
from reconcile.importer import import_data, parse_decimal
from reconcile.models import Location, SystemARecord, SystemBRecord
from reconcile.normalization import normalize_record_ref


class ImportParsingTests(TestCase):
    def test_indian_comma_blank_and_invalid_decimal(self):
        self.assertEqual(parse_decimal("1,25,400.00"), Decimal("125400.00"))
        self.assertIsNone(parse_decimal(""))
        self.assertIsNone(parse_decimal(None))
        self.assertIsNone(parse_decimal("not-a-number"))
        self.assertIsNone(parse_decimal("NaN"))

    def test_reference_normalization(self):
        self.assertEqual(normalize_record_ref("rec1034"), "REC-1034")
        self.assertEqual(normalize_record_ref("REC - 1070"), "REC-1070")
        self.assertEqual(normalize_record_ref("1112"), "REC-1112")
        self.assertIsNone(normalize_record_ref("not-a-record"))

    def test_import_loads_every_row_and_is_idempotent(self):
        expected = {
            "locations": 5,
            "system_a": 120,
            "system_b": 121,
            "system_a_saved": 120,
            "system_b_saved": 121,
            "blank_actor_ids": 1,
            "blank_values": 1,
            "normalized_refs": 3,
        }
        self.assertEqual(import_data(), expected)
        self.assertEqual(import_data(), expected)
        self.assertEqual(Location.objects.count(), 5)
        self.assertEqual(SystemARecord.objects.count(), 120)
        self.assertEqual(SystemBRecord.objects.count(), 121)

        self.assertIsNone(SystemARecord.objects.get(record_id="REC-1050").actor_id)
        self.assertIsNone(SystemBRecord.objects.get(entry_id="ENT/2026/4050").value)
        self.assertEqual(
            SystemBRecord.objects.get(entry_id="ENT/2026/4064").value,
            Decimal("125400.00"),
        )

    def test_unreadable_cells_keep_rows_and_original_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            self._write_csv(
                data_dir / "locations.csv",
                ["location_id", "org_id", "location_name"],
                [{"location_id": "LOC-A", "org_id": "ORG-A", "location_name": "Alpha"}],
            )
            self._write_csv(
                data_dir / "system_a.csv",
                [
                    "record_id", "location_id", "event_date", "base_value",
                    "adjustment", "total_value", "state", "actor_id",
                ],
                [{
                    "record_id": "REC-9000",
                    "location_id": "LOC-UNKNOWN",
                    "event_date": "not-a-date",
                    "base_value": "not-a-number",
                    "adjustment": "",
                    "total_value": "bad-total",
                    "state": "CONFIRMED",
                    "actor_id": "",
                }],
            )
            self._write_csv(
                data_dir / "system_b.csv",
                ["entry_id", "record_ref", "location_id", "recorded_on", "value"],
                [{
                    "entry_id": "ENT-9000",
                    "record_ref": "REC-9000",
                    "location_id": "LOC-A",
                    "recorded_on": "not-a-date",
                    "value": "not-a-number",
                }],
            )

            counts = import_data(data_dir=data_dir)
            self.assertEqual(counts["system_a"], counts["system_a_saved"])
            self.assertEqual(counts["system_b"], counts["system_b_saved"])
            record_a = SystemARecord.objects.get(record_id="REC-9000")
            record_b = SystemBRecord.objects.get(entry_id="ENT-9000")
            self.assertIsNone(record_a.location_id)
            self.assertIsNone(record_a.event_date)
            self.assertIsNone(record_a.base_value)
            self.assertEqual(record_a.raw_data["base_value"], "not-a-number")
            self.assertIsNone(record_b.recorded_on)
            self.assertIsNone(record_b.value)
            self.assertEqual(record_b.raw_data["value"], "not-a-number")

    def _write_csv(self, path, headers, rows):
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)


class CompareRulesTests(SimpleTestCase):
    location_orgs = {
        "LOC-A": "ORG-A",
        "LOC-A2": "ORG-A",
        "LOC-B": "ORG-B",
    }
    location_names = {
        "LOC-A": "Alpha",
        "LOC-A2": "Alpha Two",
        "LOC-B": "Beta",
    }

    def _a(self, record_id, total, location="LOC-A", state="CONFIRMED"):
        return {
            "record_id": record_id,
            "location_id": location,
            "event_date": date(2026, 4, 1),
            "base_value": Decimal("60.00"),
            "adjustment": Decimal("40.00"),
            "total_value": Decimal(total),
            "state": state,
        }

    def _b(self, entry_id, record_ref, value, location="LOC-A", label=""):
        return {
            "entry_id": entry_id,
            "record_ref": record_ref,
            "normalized_ref": normalize_record_ref(record_ref),
            "location_id": location,
            "recorded_on": date(2026, 4, 1),
            "value": Decimal(value) if value is not None else None,
            "raw_data": {"label": label},
        }

    def _compare(self, a_rows, b_rows, org="ORG-A"):
        return compare_records(
            a_rows, b_rows, self.location_orgs, self.location_names, org
        )

    def test_missing_in_b(self):
        items = self._compare([self._a("REC-0001", "100.00")], [])
        self.assertEqual(items[0]["reason"], "MISSING_IN_B")
        self.assertEqual(items[0]["record_id"], "REC-0001")

    def test_orphan_in_b(self):
        items = self._compare([], [self._b("ENT-1", "REC-9999", "42.00")])
        self.assertEqual(items[0]["reason"], "ORPHAN_IN_B")
        self.assertEqual(items[0]["b_value"], "42.00")

    def test_duplicate_in_b_when_entries_do_not_sum_to_total(self):
        items = self._compare(
            [self._a("REC-0002", "200.00")],
            [
                self._b("ENT-2A", "REC-0002", "200.00"),
                self._b("ENT-2B", "rec0002", "200.00"),
            ],
        )
        self.assertEqual(items[0]["reason"], "DUPLICATE_IN_B")
        self.assertEqual(items[0]["b_value"], "400.00")
        self.assertEqual(items[0]["difference"], "200.00")

    def test_value_mismatch_compares_against_total_value(self):
        items = self._compare(
            [self._a("REC-0004", "100.00")],
            [self._b("ENT-4", "REC-0004", "110.00")],
        )
        self.assertEqual(items[0]["reason"], "VALUE_MISMATCH")
        self.assertEqual(items[0]["a_value"], "100.00")
        self.assertEqual(items[0]["difference"], "10.00")

    def test_blank_value_is_missing_not_zero(self):
        items = self._compare(
            [self._a("REC-0005", "100.00")],
            [self._b("ENT-5", "REC-0005", None)],
        )
        self.assertEqual(items[0]["reason"], "MISSING_VALUE_IN_B")
        self.assertIsNone(items[0]["b_value"])
        self.assertIsNone(items[0]["difference"])

    def test_split_entries_that_sum_to_total_are_not_an_error(self):
        items = self._compare(
            [self._a("REC-0003", "100.00")],
            [
                self._b("ENT-3A", "REC-0003", "40.00", label="Part 1 of 2"),
                self._b("ENT-3B", "REC - 0003", "60.00", label="Part 2 of 2"),
            ],
        )
        self.assertEqual(items, [])

    def test_messy_references_match_without_false_positives(self):
        a_rows = [
            self._a("REC-1034", "1.00"),
            self._a("REC-1070", "2.00"),
            self._a("REC-1112", "3.00"),
        ]
        b_rows = [
            self._b("ENT-1034", "rec1034", "1.00"),
            self._b("ENT-1070", "REC - 1070", "2.00"),
            self._b("ENT-1112", "1112", "3.00"),
        ]
        self.assertEqual(self._compare(a_rows, b_rows), [])

    def test_matching_voided_record_is_not_flagged(self):
        items = self._compare(
            [self._a("REC-1019", "57092.35", state="VOIDED")],
            [self._b("ENT-1019", "REC-1019", "57092.35")],
        )
        self.assertEqual(items, [])

    def test_location_difference_is_missing_and_orphan_without_cross_leak(self):
        a_rows = [self._a("REC-0010", "100.00", location="LOC-A")]
        b_rows = [self._b("ENT-10", "REC-0010", "100.00", location="LOC-B")]
        org_a_items = self._compare(a_rows, b_rows, org="ORG-A")
        org_b_items = self._compare(a_rows, b_rows, org="ORG-B")
        self.assertEqual([item["reason"] for item in org_a_items], ["MISSING_IN_B"])
        self.assertEqual(org_a_items[0]["location_id"], "LOC-A")
        self.assertNotIn("LOC-B", str(org_a_items))
        self.assertEqual([item["reason"] for item in org_b_items], ["ORPHAN_IN_B"])
        self.assertEqual(org_b_items[0]["location_id"], "LOC-B")
        self.assertIsNone(org_b_items[0]["a_value"])


class ReconciliationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        location_a = Location.objects.create(
            location_id="LOC-A", org_id="ORG-A", location_name="Alpha"
        )
        Location.objects.create(
            location_id="LOC-B", org_id="ORG-B", location_name="Beta"
        )
        for record_id, system_a_value, system_b_value in (
            ("REC-0101", "20.00", "10.00"),
            ("REC-0102", "40.00", "30.00"),
        ):
            SystemARecord.objects.create(
                record_id=record_id,
                location=location_a,
                event_date=date(2026, 4, 1),
                total_value=Decimal(system_a_value),
                raw_data={},
            )
            SystemBRecord.objects.create(
                entry_id=f"ENT-{record_id}",
                record_ref=record_id,
                normalized_ref=record_id,
                location_id=location_a.location_id,
                recorded_on=date(2026, 4, 1),
                value=Decimal(system_b_value),
                raw_data={},
            )

    def test_orgs_and_required_tenant(self):
        response = self.client.get("/api/orgs/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, ["ORG-A", "ORG-B"])
        self.assertEqual(self.client.get("/api/disagreements/").status_code, 400)

    def test_reason_filter_sort_aliases_and_difference_fields(self):
        response = self.client.get(
            "/api/disagreements/",
            {"org": "ORG-A", "reason": "VALUE_MISMATCH", "sort": "desc"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertTrue(all(item["reason"] == "VALUE_MISMATCH" for item in response.data))
        self.assertEqual(response.data[0]["difference"], "-10.00")
        self.assertEqual(response.data[0]["a_value"], response.data[0]["system_a_value"])

        response = self.client.get(
            "/api/disagreements/", {"org": "ORG-A", "sort": "asc"}
        )
        self.assertEqual(
            [item["system_b_value"] for item in response.data],
            ["10.00", "30.00"],
        )
        response = self.client.get(
            "/api/disagreements/", {"org": "ORG-A", "sort": "-value"}
        )
        self.assertEqual(
            [item["system_b_value"] for item in response.data],
            ["30.00", "10.00"],
        )
