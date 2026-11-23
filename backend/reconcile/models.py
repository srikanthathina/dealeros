from django.db import models


class Location(models.Model):
    location_id = models.CharField(max_length=32, unique=True)
    org_id = models.CharField(max_length=32, db_index=True)
    location_name = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return f"{self.location_id} ({self.org_id})"


class SystemARecord(models.Model):
    record_id = models.CharField(max_length=32, unique=True)
    location = models.ForeignKey(
        Location,
        to_field="location_id",
        db_column="location_id",
        on_delete=models.PROTECT,
        related_name="system_a_records",
        null=True,
        blank=True,
    )
    event_date = models.DateField(db_index=True, null=True, blank=True)
    category_code = models.CharField(max_length=32, blank=True)
    base_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    adjustment = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    state = models.CharField(max_length=32, blank=True)
    actor_id = models.CharField(max_length=64, null=True, blank=True)
    raw_data = models.JSONField(default=dict)

    def __str__(self):
        return self.record_id


class SystemBRecord(models.Model):
    entry_id = models.CharField(max_length=64, unique=True)
    record_ref = models.CharField(max_length=64, blank=True)
    normalized_ref = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    location_id = models.CharField(max_length=32, db_index=True)
    recorded_on = models.DateField(db_index=True, null=True, blank=True)
    value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    raw_data = models.JSONField(default=dict)

    def __str__(self):
        return self.entry_id
