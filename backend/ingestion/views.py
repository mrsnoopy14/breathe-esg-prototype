"""
Ingestion API views.

Endpoint overview
-----------------
POST   /api/upload/<source_type>/    IngestionUploadView
GET    /api/ingestions/              IngestionListView
GET    /api/records/                 EmissionRecordListView
GET    /api/records/<id>/            EmissionRecordDetailView
PATCH  /api/records/<id>/            EmissionRecordDetailView
POST   /api/records/<id>/approve/    ApproveRecordView
POST   /api/records/<id>/reject/     RejectRecordView
POST   /api/records/bulk-approve/    BulkApproveView
GET    /api/stats/                   StatsView

All views are company-scoped: request.user.company filters every queryset.
"""

import traceback
from datetime import date, datetime, timezone
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Count
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditLog, DataIngestion, EmissionRecord
from .serializers import (
    ApproveRejectSerializer,
    DataIngestionSerializer,
    EmissionRecordListSerializer,
    EmissionRecordSerializer,
)
from .parsers.sap import parse_sap_fuel, parse_sap_procurement
from .parsers.utility import parse_utility_electricity
from .parsers.travel import parse_travel
from .services.normalizer import (
    normalize_sap_fuel_record,
    normalize_sap_procurement_record,
    normalize_travel_record,
    normalize_utility_record,
)
from .services.flagging import flag_record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snapshot(record: EmissionRecord) -> dict:
    """Capture a minimal state snapshot for audit log before/after fields."""
    return {
        'status': record.status,
        'co2e_kg': str(record.co2e_kg),
        'is_locked': record.is_locked,
        'review_note': record.review_note,
    }


def _create_audit_log(record: EmissionRecord, action: str, user, before: dict, after: dict, note: str = '') -> None:
    AuditLog.objects.create(
        record=record,
        action=action,
        performed_by=user,
        before_state=before,
        after_state=after,
        note=note,
    )


# ---------------------------------------------------------------------------
# Parser dispatch
# ---------------------------------------------------------------------------

def _dispatch_parser(source_type: str, filepath: str) -> tuple[list[dict], list[dict]]:
    """Call the correct parser based on source_type string."""
    if source_type == DataIngestion.SOURCE_SAP_FUEL:
        return parse_sap_fuel(filepath)
    elif source_type == DataIngestion.SOURCE_SAP_PROCUREMENT:
        return parse_sap_procurement(filepath)
    elif source_type == DataIngestion.SOURCE_UTILITY_ELECTRICITY:
        return parse_utility_electricity(filepath)
    elif source_type == DataIngestion.SOURCE_TRAVEL:
        return parse_travel(filepath)
    else:
        raise ValueError(f"Unknown source_type: '{source_type}'")


def _dispatch_normalizer(source_type: str, row: dict, company) -> dict:
    """Call the correct normalizer based on source_type string."""
    if source_type == DataIngestion.SOURCE_SAP_FUEL:
        return normalize_sap_fuel_record(row, company)
    elif source_type == DataIngestion.SOURCE_SAP_PROCUREMENT:
        return normalize_sap_procurement_record(row, company)
    elif source_type == DataIngestion.SOURCE_UTILITY_ELECTRICITY:
        return normalize_utility_record(row, company)
    elif source_type == DataIngestion.SOURCE_TRAVEL:
        return normalize_travel_record(row, company)
    else:
        raise ValueError(f"Unknown source_type: '{source_type}'")


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class RecordPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

class IngestionUploadView(APIView):
    """
    POST /api/upload/<source_type>/

    Multipart form data: file=<file object>

    Parses the file, normalizes each row, flags anomalies, and persists
    EmissionRecords + one AuditLog per record — all inside a single DB
    transaction so partial failures don't leave orphaned records.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, source_type: str):
        company = request.user.company
        if company is None:
            return Response(
                {'detail': 'Your account is not linked to a company.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        valid_source_types = dict(DataIngestion.SOURCE_CHOICES).keys()
        if source_type not in valid_source_types:
            return Response(
                {'detail': f"Invalid source_type '{source_type}'. "
                           f"Valid values: {list(valid_source_types)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'detail': 'No file uploaded. Send the file as multipart field "file".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create the DataIngestion record immediately so we have an ID
        ingestion = DataIngestion.objects.create(
            company=company,
            source_type=source_type,
            original_filename=uploaded_file.name,
            file=uploaded_file,
            uploaded_by=request.user,
            status=DataIngestion.STATUS_PROCESSING,
        )

        # Write the file to disk so parsers can open it by path
        file_path = ingestion.file.path

        try:
            parsed_rows, parse_errors = _dispatch_parser(source_type, file_path)
        except ValueError as exc:
            ingestion.status = DataIngestion.STATUS_FAILED
            ingestion.error_log = [{'row': 0, 'error': str(exc)}]
            ingestion.save()
            return Response(
                {'detail': str(exc), 'ingestion_id': ingestion.id},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ingestion.row_count = len(parsed_rows) + len(parse_errors)
        ingestion.error_count = len(parse_errors)
        ingestion.error_log = parse_errors

        # Normalize + flag + persist inside one transaction
        records_created = 0
        normalizer_errors: list[dict] = []

        # Pre-fetch existing records for this company+category for outlier detection
        # We group them lazily per category to avoid N+1 when all rows are the same category
        _category_cache: dict[str, list[dict]] = {}

        def _get_existing(category: str) -> list[dict]:
            if category not in _category_cache:
                _category_cache[category] = list(
                    EmissionRecord.objects.filter(
                        company=company, category=category
                    ).values('co2e_kg')
                )
            return _category_cache[category]

        try:
            with transaction.atomic():
                for row_idx, row in enumerate(parsed_rows, start=1):
                    try:
                        normalized = _dispatch_normalizer(source_type, row, company)

                        # Strip private flag hints before building model kwargs
                        private_keys = [k for k in normalized if k.startswith('_')]
                        flags, flag_reasons = flag_record(
                            normalized,
                            _get_existing(normalized.get('category', '')),
                        )
                        for k in private_keys:
                            normalized.pop(k)

                        # Determine status — flagged if any flag fired
                        rec_status = (
                            EmissionRecord.STATUS_FLAGGED
                            if any(flags.values())
                            else EmissionRecord.STATUS_PENDING
                        )

                        record = EmissionRecord.objects.create(
                            ingestion=ingestion,
                            flags=flags,
                            flag_reasons=flag_reasons,
                            status=rec_status,
                            **normalized,
                        )

                        # Update cache so next rows in same category include this one
                        _category_cache.setdefault(record.category, []).append(
                            {'co2e_kg': record.co2e_kg}
                        )

                        _create_audit_log(
                            record=record,
                            action='INGESTED',
                            user=request.user,
                            before={},
                            after=_snapshot(record),
                            note=f"Ingested from {ingestion.original_filename}",
                        )
                        records_created += 1

                    except Exception as exc:
                        normalizer_errors.append({
                            'row': row_idx,
                            'error': f"Normalization failed: {exc}",
                        })

                ingestion.parsed_count = records_created
                ingestion.error_count = len(parse_errors) + len(normalizer_errors)
                ingestion.error_log = parse_errors + normalizer_errors
                ingestion.status = DataIngestion.STATUS_COMPLETED
                ingestion.save()

        except Exception:
            ingestion.status = DataIngestion.STATUS_FAILED
            ingestion.error_log = [{'row': 0, 'error': traceback.format_exc()}]
            ingestion.save()
            return Response(
                {'detail': 'Unexpected error during processing.', 'ingestion_id': ingestion.id},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            DataIngestionSerializer(ingestion).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Ingestion list
# ---------------------------------------------------------------------------

class IngestionListView(generics.ListAPIView):
    """GET /api/ingestions/ — list all uploads for the current company."""

    serializer_class = DataIngestionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DataIngestion.objects.filter(
            company=self.request.user.company
        ).order_by('-uploaded_at')


# ---------------------------------------------------------------------------
# Emission record list
# ---------------------------------------------------------------------------

class EmissionRecordListView(generics.ListAPIView):
    """
    GET /api/records/

    Query params:
      status        — PENDING | FLAGGED | APPROVED | REJECTED
      scope         — 1 | 2 | 3
      source_type   — SAP_FUEL | SAP_PROCUREMENT | UTILITY_ELECTRICITY | TRAVEL
      date_from     — YYYY-MM-DD
      date_to       — YYYY-MM-DD
    """

    serializer_class = EmissionRecordListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = RecordPagination

    def get_queryset(self):
        qs = EmissionRecord.objects.filter(
            company=self.request.user.company
        ).select_related('ingestion', 'reviewed_by')

        params = self.request.query_params

        if status_filter := params.get('status'):
            qs = qs.filter(status=status_filter.upper())

        if scope := params.get('scope'):
            try:
                qs = qs.filter(scope=int(scope))
            except ValueError:
                pass

        if source_type := params.get('source_type'):
            qs = qs.filter(ingestion__source_type=source_type.upper())

        if date_from := params.get('date_from'):
            try:
                qs = qs.filter(activity_date__gte=date.fromisoformat(date_from))
            except ValueError:
                pass

        if date_to := params.get('date_to'):
            try:
                qs = qs.filter(activity_date__lte=date.fromisoformat(date_to))
            except ValueError:
                pass

        return qs.order_by('-activity_date')


# ---------------------------------------------------------------------------
# Emission record detail + update
# ---------------------------------------------------------------------------

class EmissionRecordDetailView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/records/<id>/   — full record detail
    PATCH /api/records/<id>/  — edit mutable fields (locked records rejected)

    Editable fields: activity_date, description, co2e_kg, review_note.
    Every change is appended to edit_history and an EDITED AuditLog is created.
    """

    serializer_class = EmissionRecordSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        return EmissionRecord.objects.filter(company=self.request.user.company)

    def partial_update(self, request, *args, **kwargs):
        record = self.get_object()

        if record.is_locked:
            return Response(
                {'detail': 'This record is locked for audit and cannot be edited.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Fields an analyst is allowed to change
        editable_fields = {'activity_date', 'description', 'co2e_kg', 'review_note'}
        incoming = {k: v for k, v in request.data.items() if k in editable_fields}

        if not incoming:
            return Response(
                {'detail': f"No editable fields provided. Editable: {editable_fields}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        before = _snapshot(record)
        history_entries = []
        now_str = datetime.now(tz=timezone.utc).isoformat()

        for field, new_value in incoming.items():
            old_value = getattr(record, field)
            if str(old_value) != str(new_value):
                history_entries.append({
                    'field': field,
                    'old': str(old_value),
                    'new': str(new_value),
                    'by': request.user.username,
                    'at': now_str,
                })
                setattr(record, field, new_value)

        if history_entries:
            record.is_edited = True
            record.edit_history = (record.edit_history or []) + history_entries
            record.save()

            after = _snapshot(record)
            _create_audit_log(
                record=record,
                action='EDITED',
                user=request.user,
                before=before,
                after=after,
                note=f"Fields edited: {[e['field'] for e in history_entries]}",
            )

        return Response(EmissionRecordSerializer(record).data)


# ---------------------------------------------------------------------------
# Approve / Reject
# ---------------------------------------------------------------------------

class ApproveRecordView(APIView):
    """POST /api/records/<id>/approve/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        try:
            record = EmissionRecord.objects.get(
                pk=pk, company=request.user.company
            )
        except EmissionRecord.DoesNotExist:
            return Response({'detail': 'Record not found.'}, status=status.HTTP_404_NOT_FOUND)

        if record.is_locked:
            return Response(
                {'detail': 'Locked records cannot be approved.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if record.status not in (EmissionRecord.STATUS_PENDING, EmissionRecord.STATUS_FLAGGED):
            return Response(
                {'detail': f"Cannot approve a record with status '{record.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ApproveRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        before = _snapshot(record)
        record.status = EmissionRecord.STATUS_APPROVED
        record.reviewed_by = request.user
        record.reviewed_at = datetime.now(tz=timezone.utc)
        record.review_note = serializer.validated_data.get('review_note', '')
        record.save()

        _create_audit_log(
            record=record,
            action='APPROVED',
            user=request.user,
            before=before,
            after=_snapshot(record),
            note=record.review_note,
        )

        return Response(EmissionRecordSerializer(record).data)


class RejectRecordView(APIView):
    """POST /api/records/<id>/reject/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        try:
            record = EmissionRecord.objects.get(
                pk=pk, company=request.user.company
            )
        except EmissionRecord.DoesNotExist:
            return Response({'detail': 'Record not found.'}, status=status.HTTP_404_NOT_FOUND)

        if record.is_locked:
            return Response(
                {'detail': 'Locked records cannot be rejected.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if record.status not in (EmissionRecord.STATUS_PENDING, EmissionRecord.STATUS_FLAGGED):
            return Response(
                {'detail': f"Cannot reject a record with status '{record.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ApproveRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        before = _snapshot(record)
        record.status = EmissionRecord.STATUS_REJECTED
        record.reviewed_by = request.user
        record.reviewed_at = datetime.now(tz=timezone.utc)
        record.review_note = serializer.validated_data.get('review_note', '')
        record.save()

        _create_audit_log(
            record=record,
            action='REJECTED',
            user=request.user,
            before=before,
            after=_snapshot(record),
            note=record.review_note,
        )

        return Response(EmissionRecordSerializer(record).data)


# ---------------------------------------------------------------------------
# Bulk approve
# ---------------------------------------------------------------------------

class BulkApproveView(APIView):
    """
    POST /api/records/bulk-approve/

    Body: {"record_ids": [1, 2, 3]}

    Approves all non-locked PENDING or FLAGGED records in the list that
    belong to the current company.  Skips locked / already-reviewed records
    and reports them in the response.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        record_ids = request.data.get('record_ids', [])
        if not isinstance(record_ids, list) or not record_ids:
            return Response(
                {'detail': 'Provide a non-empty list in "record_ids".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only operate on records belonging to this company
        candidates = EmissionRecord.objects.filter(
            pk__in=record_ids,
            company=request.user.company,
        )

        approved_ids: list[int] = []
        skipped: list[dict] = []
        now = datetime.now(tz=timezone.utc)

        with transaction.atomic():
            for record in candidates:
                if record.is_locked:
                    skipped.append({'id': record.id, 'reason': 'locked'})
                    continue
                if record.status not in (EmissionRecord.STATUS_PENDING, EmissionRecord.STATUS_FLAGGED):
                    skipped.append({'id': record.id, 'reason': f'status is {record.status}'})
                    continue

                before = _snapshot(record)
                record.status = EmissionRecord.STATUS_APPROVED
                record.reviewed_by = request.user
                record.reviewed_at = now
                record.review_note = 'Bulk approved'
                record.save()

                _create_audit_log(
                    record=record,
                    action='APPROVED',
                    user=request.user,
                    before=before,
                    after=_snapshot(record),
                    note='Bulk approved',
                )
                approved_ids.append(record.id)

        return Response({
            'approved': approved_ids,
            'approved_count': len(approved_ids),
            'skipped': skipped,
        })


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class StatsView(APIView):
    """
    GET /api/stats/

    Returns a dashboard summary for the current company:
      total_co2e_by_scope     — {1: x, 2: x, 3: x}
      records_by_status       — {PENDING: n, FLAGGED: n, APPROVED: n, REJECTED: n}
      recent_ingestions       — last 5 DataIngestion records
      co2e_by_category        — {category: total_co2e}
      monthly_co2e            — [{month: '2024-01', co2e: x}, ...]  (last 24 months)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = request.user.company
        if company is None:
            return Response({'detail': 'No company linked.'}, status=status.HTTP_403_FORBIDDEN)

        base_qs = EmissionRecord.objects.filter(company=company)

        # --- CO2e by scope ---
        scope_data = (
            base_qs
            .values('scope')
            .annotate(total=Sum('co2e_kg'))
            .order_by('scope')
        )
        total_co2e_by_scope = {1: 0.0, 2: 0.0, 3: 0.0}
        for row in scope_data:
            if row['scope'] in total_co2e_by_scope:
                total_co2e_by_scope[row['scope']] = float(row['total'] or 0)

        # --- Records by status ---
        status_data = (
            base_qs
            .values('status')
            .annotate(count=Count('id'))
        )
        records_by_status = {
            'PENDING': 0,
            'FLAGGED': 0,
            'APPROVED': 0,
            'REJECTED': 0,
        }
        for row in status_data:
            records_by_status[row['status']] = row['count']

        # --- Recent ingestions ---
        recent_ingestions = DataIngestion.objects.filter(
            company=company
        ).order_by('-uploaded_at')[:5]

        # --- CO2e by category ---
        category_data = (
            base_qs
            .values('category')
            .annotate(total=Sum('co2e_kg'))
            .order_by('category')
        )
        co2e_by_category = {
            row['category']: float(row['total'] or 0)
            for row in category_data
        }

        # --- Monthly CO2e (last 24 calendar months) ---
        # We compute this in Python to keep it DB-agnostic (SQLite doesn't
        # have DATE_TRUNC; PostgreSQL does but we want both to work).
        from collections import defaultdict
        monthly: dict[str, float] = defaultdict(float)
        monthly_records = base_qs.values('activity_date', 'co2e_kg')
        for row in monthly_records:
            month_key = row['activity_date'].strftime('%Y-%m')
            monthly[month_key] += float(row['co2e_kg'] or 0)

        # Sort and limit to last 24 months
        monthly_co2e = sorted(
            [{'month': k, 'co2e': round(v, 4)} for k, v in monthly.items()],
            key=lambda x: x['month'],
        )[-24:]

        return Response({
            'total_co2e_by_scope': total_co2e_by_scope,
            'records_by_status': records_by_status,
            'recent_ingestions': DataIngestionSerializer(recent_ingestions, many=True).data,
            'co2e_by_category': co2e_by_category,
            'monthly_co2e': monthly_co2e,
        })
