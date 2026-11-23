# Decisions

## Decision: Normalize references before matching
- Rejected: Match the raw `record_ref` string exactly.
- Why: `rec1034`, `REC - 1070`, and `1112` are alternate spellings of canonical `REC-XXXX` IDs.

## Decision: Keep unreadable amounts as null and preserve their source text
- Rejected: Convert blanks or invalid amounts to zero, or discard the row.
- Why: Zero is a real amount; `raw_data` keeps the original text for review.

## Decision: Compare System B with System A's `total_value`
- Rejected: Compare with `base_value`.
- Why: `total_value` includes adjustments and is the amount System B records.

## Decision: Ignore a correctly summed split; flag an unbalanced duplicate
- Rejected: Flag every record with multiple System B entries.
- Why: `REC-1055` has two entries that sum to A's total; `REC-1042` has two full entries and totals twice A's value.

## Decision: Reconcile `VOIDED` rows by the same value and location rules
- Rejected: Assume a B entry for a voided A row is automatically invalid.
- Why: B has no void/cancellation status, and the actual `REC-1019` entry matches A's total, location, and date. The state remains available in the raw record.

## Decision: Treat location differences as missing/orphan findings; do not flag date-only differences
- Rejected: Add separate `LOCATION_MISMATCH` and `DATE_MISMATCH` reasons in this version.
- Why: A location-mismatched A row is missing at its own location, while the B row is orphaned at its own location. Dates are preserved but do not define record identity.

## Decision: Scope both database queries and pure comparison input by the location map
- Rejected: Fetch all tenants' rows and hide rows only in the frontend.
- Why: `locations.csv` is the tenant authority; the API selects one org in SQL, and the comparison function applies the same location mapping.

## Decision: Keep an orphan on the tenant that owns its System B location
- Rejected: Include the other tenant's A-side location or amount in the finding.
- Why: The cross-org `REC-1077` is missing under A's location for ORG-A and shown as an ORG-B orphan using only B's location and value.

## Decision: Use SQLite, `Decimal`, and source-row JSON
- Rejected: Add a separate database service, use binary floats, or discard unmodeled source columns.
- Why: SQLite is sufficient for this assessment; `Decimal` keeps money exact, and `raw_data` retains every imported column.
