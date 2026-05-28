from django.contrib import admin

from .models import AuditLog, DataIngestion, EmissionRecord


@admin.register(DataIngestion)
class DataIngestionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'company', 'source_type', 'original_filename',
        'status', 'row_count', 'parsed_count', 'error_count', 'uploaded_at',
    )
    list_filter = ('status', 'source_type', 'company')
    search_fields = ('original_filename', 'company__name')
    readonly_fields = ('uploaded_at', 'error_log')
    ordering = ('-uploaded_at',)


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'company', 'category', 'scope', 'activity_date',
        'co2e_kg', 'status', 'is_locked', 'is_edited',
    )
    list_filter = ('status', 'scope', 'category', 'company', 'is_locked', 'is_edited')
    search_fields = ('description', 'source_plant_code', 'source_vendor', 'source_material')
    readonly_fields = (
        'raw_source_data', 'edit_history', 'created_at', 'updated_at',
        'reviewed_by', 'reviewed_at',
    )
    ordering = ('-activity_date',)

    fieldsets = (
        ('Tenancy & Provenance', {
            'fields': ('company', 'ingestion'),
        }),
        ('GHG Classification', {
            'fields': ('scope', 'category'),
        }),
        ('Activity Data', {
            'fields': (
                'activity_date', 'description',
                'raw_quantity', 'raw_unit',
                'normalized_quantity', 'normalized_unit',
            ),
        }),
        ('Emission Calculation', {
            'fields': ('co2e_kg', 'emission_factor', 'emission_factor_source'),
        }),
        ('Source Metadata', {
            'fields': (
                'source_plant_code', 'source_meter_id', 'source_record_id',
                'source_vendor', 'source_material',
            ),
        }),
        ('Review Workflow', {
            'fields': (
                'status', 'flags', 'flag_reasons',
                'reviewed_by', 'reviewed_at', 'review_note',
                'is_locked',
            ),
        }),
        ('Audit Trail', {
            'fields': ('is_edited', 'edit_history', 'raw_source_data', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'record', 'action', 'performed_by', 'performed_at')
    list_filter = ('action',)
    search_fields = ('record__id', 'performed_by__username', 'note')
    readonly_fields = ('record', 'action', 'performed_by', 'performed_at', 'before_state', 'after_state', 'note')
    ordering = ('-performed_at',)

    def has_add_permission(self, request):
        # Audit logs are append-only; nobody should create them from the admin.
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
