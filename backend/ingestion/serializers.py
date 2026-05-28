"""
Serializers for the ingestion app.

Hierarchy:
  DataIngestionSerializer        — full ingestion batch record
  EmissionRecordSerializer       — full record (detail view, includes raw data)
  EmissionRecordListSerializer   — lighter version for list views
  ApproveRejectSerializer        — payload for approve/reject endpoints
"""

from rest_framework import serializers

from .models import AuditLog, DataIngestion, EmissionRecord


class DataIngestionSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.SerializerMethodField()

    class Meta:
        model = DataIngestion
        fields = (
            'id',
            'source_type',
            'original_filename',
            'file',
            'uploaded_by',
            'uploaded_by_username',
            'uploaded_at',
            'status',
            'row_count',
            'parsed_count',
            'error_count',
            'error_log',
        )
        read_only_fields = fields

    def get_uploaded_by_username(self, obj) -> str | None:
        if obj.uploaded_by:
            return obj.uploaded_by.username
        return None


class EmissionRecordSerializer(serializers.ModelSerializer):
    """
    Full record representation used in detail views.
    Includes raw_source_data and edit_history which are intentionally omitted
    from the list serializer to keep list payloads small.
    """
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = (
            'id',
            'company',
            'ingestion',
            'scope',
            'category',
            'activity_date',
            'description',
            'raw_quantity',
            'raw_unit',
            'normalized_quantity',
            'normalized_unit',
            'co2e_kg',
            'emission_factor',
            'emission_factor_source',
            'source_plant_code',
            'source_meter_id',
            'source_record_id',
            'source_vendor',
            'source_material',
            'raw_source_data',
            'status',
            'flags',
            'flag_reasons',
            'reviewed_by',
            'reviewed_by_name',
            'reviewed_at',
            'review_note',
            'is_locked',
            'is_edited',
            'edit_history',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id', 'company', 'ingestion', 'scope', 'category',
            'raw_source_data', 'is_locked', 'is_edited', 'edit_history',
            'reviewed_by', 'reviewed_by_name', 'reviewed_at',
            'emission_factor', 'emission_factor_source',
            'created_at', 'updated_at',
        )

    def get_reviewed_by_name(self, obj) -> str | None:
        if obj.reviewed_by:
            return obj.reviewed_by.username
        return None


class EmissionRecordListSerializer(serializers.ModelSerializer):
    """
    Lightweight list view — omits raw_source_data and edit_history
    to keep bandwidth low when returning 50 records per page.
    """
    reviewed_by_name = serializers.SerializerMethodField()
    ingestion_source_type = serializers.CharField(source='ingestion.source_type', read_only=True)

    class Meta:
        model = EmissionRecord
        fields = (
            'id',
            'company',
            'ingestion',
            'ingestion_source_type',
            'scope',
            'category',
            'activity_date',
            'description',
            'raw_quantity',
            'raw_unit',
            'normalized_quantity',
            'normalized_unit',
            'co2e_kg',
            'emission_factor_source',
            'source_plant_code',
            'source_meter_id',
            'source_vendor',
            'status',
            'flags',
            'flag_reasons',
            'reviewed_by',
            'reviewed_by_name',
            'reviewed_at',
            'is_locked',
            'is_edited',
            'created_at',
        )
        read_only_fields = fields

    def get_reviewed_by_name(self, obj) -> str | None:
        if obj.reviewed_by:
            return obj.reviewed_by.username
        return None


class ApproveRejectSerializer(serializers.Serializer):
    """Payload for the approve and reject endpoints.  Only the note is user-supplied."""

    review_note = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        help_text="Optional note explaining the approval/rejection decision.",
    )


class AuditLogSerializer(serializers.ModelSerializer):
    performed_by_username = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            'id',
            'record',
            'action',
            'performed_by',
            'performed_by_username',
            'performed_at',
            'before_state',
            'after_state',
            'note',
        )
        read_only_fields = fields

    def get_performed_by_username(self, obj) -> str | None:
        if obj.performed_by:
            return obj.performed_by.username
        return None
