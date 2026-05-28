from django.db import models
from accounts.models import Company, User


class DataIngestion(models.Model):
    """Tracks every file upload. Immutable once created — source of truth for provenance."""
    SOURCE_SAP_FUEL = 'SAP_FUEL'
    SOURCE_SAP_PROCUREMENT = 'SAP_PROCUREMENT'
    SOURCE_UTILITY_ELECTRICITY = 'UTILITY_ELECTRICITY'
    SOURCE_TRAVEL = 'TRAVEL'
    SOURCE_CHOICES = [
        (SOURCE_SAP_FUEL, 'SAP Fuel (MB51)'),
        (SOURCE_SAP_PROCUREMENT, 'SAP Procurement (ME2N)'),
        (SOURCE_UTILITY_ELECTRICITY, 'Utility Electricity (Green Button CSV)'),
        (SOURCE_TRAVEL, 'Corporate Travel (Concur Export)'),
    ]

    STATUS_QUEUED = 'QUEUED'
    STATUS_PROCESSING = 'PROCESSING'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_FAILED = 'FAILED'
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='ingestions')
    source_type = models.CharField(max_length=30, choices=SOURCE_CHOICES)
    original_filename = models.CharField(max_length=500)
    file = models.FileField(upload_to='uploads/%Y/%m/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    row_count = models.IntegerField(default=0)
    parsed_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    error_log = models.JSONField(default=list)  # [{row, error}, ...]

    def __str__(self):
        return f"{self.source_type} — {self.original_filename} ({self.uploaded_at.date()})"


class EmissionRecord(models.Model):
    """
    One normalized, source-tracked emission activity row.
    Immutable source data lives in raw_source_data; all edits recorded in edit_history.
    """
    SCOPE_1 = 1
    SCOPE_2 = 2
    SCOPE_3 = 3
    SCOPE_CHOICES = [(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')]

    CATEGORY_FUEL_COMBUSTION = 'fuel_combustion'
    CATEGORY_PURCHASED_ELECTRICITY = 'purchased_electricity'
    CATEGORY_BUSINESS_TRAVEL_AIR = 'business_travel_air'
    CATEGORY_BUSINESS_TRAVEL_HOTEL = 'business_travel_hotel'
    CATEGORY_BUSINESS_TRAVEL_GROUND = 'business_travel_ground'
    CATEGORY_PURCHASED_GOODS = 'purchased_goods'
    CATEGORY_CHOICES = [
        (CATEGORY_FUEL_COMBUSTION, 'Fuel Combustion'),
        (CATEGORY_PURCHASED_ELECTRICITY, 'Purchased Electricity'),
        (CATEGORY_BUSINESS_TRAVEL_AIR, 'Business Travel — Air'),
        (CATEGORY_BUSINESS_TRAVEL_HOTEL, 'Business Travel — Hotel'),
        (CATEGORY_BUSINESS_TRAVEL_GROUND, 'Business Travel — Ground'),
        (CATEGORY_PURCHASED_GOODS, 'Purchased Goods & Services'),
    ]

    STATUS_PENDING = 'PENDING'
    STATUS_FLAGGED = 'FLAGGED'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_FLAGGED, 'Flagged'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    # Tenancy and provenance
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='emission_records')
    ingestion = models.ForeignKey(DataIngestion, on_delete=models.CASCADE, related_name='records')

    # GHG classification
    scope = models.IntegerField(choices=SCOPE_CHOICES)
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)

    # Activity data
    activity_date = models.DateField()
    description = models.CharField(max_length=500, blank=True)
    raw_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    raw_unit = models.CharField(max_length=20)  # as-received unit

    # Normalized activity (base units per category)
    # Fuel: liters | Electricity: kWh | Air travel: passenger-km | Hotel: room-nights | Ground: km
    normalized_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    normalized_unit = models.CharField(max_length=20)

    # Emission calculation
    co2e_kg = models.DecimalField(max_digits=18, decimal_places=4)
    emission_factor = models.DecimalField(max_digits=12, decimal_places=6)
    emission_factor_source = models.CharField(max_length=100)  # e.g. 'DEFRA_2023'

    # Source metadata (vary by source type)
    source_plant_code = models.CharField(max_length=50, blank=True)   # SAP: WERKS
    source_meter_id = models.CharField(max_length=100, blank=True)    # Utility: meter number
    source_record_id = models.CharField(max_length=100, blank=True)   # original row identifier
    source_vendor = models.CharField(max_length=255, blank=True)      # SAP procurement vendor
    source_material = models.CharField(max_length=255, blank=True)    # SAP material description

    # Raw original row (immutable, never edited)
    raw_source_data = models.JSONField(default=dict)

    # Review workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    flags = models.JSONField(default=dict)         # {flag_name: True/False}
    flag_reasons = models.JSONField(default=list)  # ['Quantity 4.2x above monthly average', ...]

    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_records',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    # Audit lock — set after audit export, prevents further editing
    is_locked = models.BooleanField(default=False)

    # Edit tracking
    is_edited = models.BooleanField(default=False)
    edit_history = models.JSONField(default=list)  # [{field, old, new, by, at}, ...]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activity_date']

    def __str__(self):
        return f"{self.category} | {self.activity_date} | {self.co2e_kg} kgCO2e"


class AuditLog(models.Model):
    """Append-only log of every state change. Never edited or deleted."""
    ACTION_CHOICES = [
        ('INGESTED', 'Ingested'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('FLAGGED', 'Flagged'),
        ('EDITED', 'Edited'),
        ('LOCKED', 'Locked'),
    ]

    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    before_state = models.JSONField(default=dict)
    after_state = models.JSONField(default=dict)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['performed_at']
