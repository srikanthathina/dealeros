import re


def normalize_record_ref(record_ref):
    """Convert supported reference spellings to canonical REC-XXXX form."""
    compact = re.sub(r"[^A-Z0-9]", "", str(record_ref or "").upper())
    digits = compact[3:] if compact.startswith("REC") else compact
    if not digits.isdigit():
        return None
    return f"REC-{digits.zfill(4)}"
